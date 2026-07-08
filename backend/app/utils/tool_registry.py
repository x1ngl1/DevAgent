"""Tool registry - manage available tools and built-in implementations"""
import asyncio, json, logging, time, httpx
from typing import Dict, Any, List, Optional, Callable
from app.utils.tool_base import ToolDef, ToolResult
from app.config import TOOL_TIMEOUT
logger = logging.getLogger(__name__)
class ToolRegistry:
    _tools: Dict[str, ToolDef] = {}
    _status_callback = None
    @classmethod
    def set_status_callback(cls, cb): cls._status_callback = cb
    @classmethod
    def register(cls, t): cls._tools[t.name] = t; logger.info(f"Registered: {t.name}")
    @classmethod
    def get_tool_defs(cls, cats=None): return [t.to_openai_tool() for t in cls._tools.values() if not cats or t.category in cats]
    @classmethod
    async def execute(cls, name, args, ctx=None):
        t = cls._tools.get(name)
        if not t: return ToolResult(success=False, error=f"Unknown: {name}")
        if cls._status_callback: await cls._status_callback({"type":"tool_call_start","tool_name":name,"args":args})
        try:
            r = await t.run(args, ctx or {})
            if cls._status_callback: await cls._status_callback({"type":"tool_call_done","tool_name":name,"success":r.success,"result_preview":str(r)[:200]})
            return r
        except Exception as e: return ToolResult(success=False, error=str(e))
    @classmethod
    async def execute_tool_calls(cls, calls, ctx=None):
        results = await asyncio.gather(*[cls.execute(c["function"]["name"],json.loads(c["function"]["arguments"]),ctx) for c in calls], return_exceptions=True)
        return [{"role":"tool","tool_call_id":c["id"],"content":json.dumps((ToolResult(success=False,error=str(r)) if isinstance(r,Exception) else r).to_dict(),ensure_ascii=False)} for c,r in zip(calls,results)]

async def _web_search(a, ctx):
    """网络搜索工具 — 多源搜索（天气专用API + Bing + DuckDuckGo）"""
    q = a.get("query","")
    if not q: return ToolResult(success=False,error="No query")
    results = []
    q_lower = q.lower()

    # ── A) 天气查询优先用 wttr.in 专用 API ──
    if "天气" in q or "weather" in q_lower or "温度" in q or "气温" in q:
        import re
        # 提取城市名
        city = q
        for kw in ["天气", "weather", "温度", "气温", "怎么样", "如何", "今天", "现在", "?"]:
            city = city.replace(kw, "").strip()
        # 去掉标点和空白
        city = re.sub(r'[？?，,。.!！：: ]', '', city).strip()
        if not city or len(city) > 6:
            city = "Beijing" if "bj" in q_lower or "北京" in q else "Shanghai"

        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"https://wttr.in/{city}?format=%C+%t+%h+%w&lang=zh",
                                headers={"User-Agent": "curl/8.0"})
                if r.status_code == 200:
                    weather_text = r.text.strip()
                    if weather_text and "Unknown" not in weather_text:
                        results.append({
                            "text": f"{city}当前天气：{weather_text}",
                            "source": "wttr.in"
                        })
        except Exception as e:
            logger.warning(f"Weather API failed: {str(e)[:60]}")

        # 再试一次用中文格式
        if not results:
            try:
                async with httpx.AsyncClient(timeout=8) as c:
                    r = await c.get(f"https://wttr.in/{city}?format=%C+%t+%h+%w&lang=zh",
                                    headers={"User-Agent": "curl/8.0"})
                    if r.status_code == 200:
                        wt = r.text.strip()
                        if wt and "Unknown" not in wt:
                            results.append({"text": f"{city}实时天气：{wt}"})
            except Exception:
                pass

    # ── B) Bing 搜索（国内可访问） ──
    if not results:
        bing_urls = [
            f"https://www.bing.com/search?q={q}&setlang=zh-Hans",
        ]
        for url in bing_urls:
            try:
                async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
                    r = await c.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "text/html",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                    })
                    if r.status_code != 200:
                        continue
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(r.text, "html.parser")
                    for li in soup.select("li.b_algo") or soup.select(".b_algo") or soup.select("#b_results > li"):
                        a_tag = li.select_one("h2 a") or li.select_one("a")
                        snippet_tag = li.select_one(".b_caption p") or li.select_one("p")
                        if a_tag:
                            href = a_tag.get("href", "")
                            text = a_tag.get_text(strip=True)
                            snippet = snippet_tag.get_text(strip=True)[:200] if snippet_tag else ""
                            if text and href:
                                results.append({"text": text, "snippet": snippet, "url": href})
                                if len(results) >= 5:
                                    break
                    if results:
                        break
            except Exception as e:
                logger.warning(f"Bing search failed: {str(e)[:60]}")
                continue

    # ── C) DuckDuckGo 作为备选 ──
    if not results:
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=True) as c:
                r = await c.post("https://lite.duckduckgo.com/lite/", data={"q": q},
                                 headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
                if r.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(r.text, "html.parser")
                    for tr in soup.select("tr")[:15]:
                        txt = tr.get_text(" ", strip=True)
                        if len(txt) > 30:
                            results.append({"text": txt[:300]})
        except Exception as e:
            logger.warning(f"DDG fallback failed: {str(e)[:60]}")

    # ── 返回结果 ──
    if results:
        return ToolResult(success=True, data=results, content_type="json")

    return ToolResult(success=True, data=[{
        "text": f"关于'{q}'的实时搜索结果暂未获取到，可基于自身知识回答。"
    }], content_type="json")

async def _http_request(a, ctx):
    m,u,h,b = a.get("method","GET").upper(),a.get("url",""),a.get("headers",{}),a.get("body")
    if not u: return ToolResult(success=False,error="No URL")
    try:
        async with httpx.AsyncClient(timeout=TOOL_TIMEOUT,verify=False) as c:
            r = await {"GET":c.get(u,headers=h),"POST":c.post(u,headers=h,json=b),"PUT":c.put(u,headers=h,json=b),"DELETE":c.delete(u,headers=h)}.get(m,c.get(u))
            try: return ToolResult(success=True,data=r.json(),content_type="json")
            except: return ToolResult(success=True,data=r.text[:5000])
    except Exception as e: return ToolResult(success=False,error=f"HTTP:{str(e)[:150]}")

async def _run_python(a, ctx):
    try:
        from app.services.sandbox import SandboxService
        r = await SandboxService().run_code(a.get("code",""))
        return ToolResult(success=r.get("success",False),data=r.get("output",r.get("error","No output")))
    except Exception as e: return ToolResult(success=False,error=f"Exec:{str(e)[:150]}")

async def _read_project_file(a, ctx):
    import os; p = a.get("path","")
    if not p: return ToolResult(success=False,error="No path")
    rp = os.path.realpath(p)
    prefixes = ["/root/Agent/backend/outputs","/root/Agent/backend/app","/root/Agent/frontend/src"]
    if not any(rp.startswith(os.path.realpath(pre)) for pre in prefixes): return ToolResult(success=False,error="Not allowed")
    try:
        with open(rp,"r",encoding="utf-8") as f: return ToolResult(success=True,data=f.read()[:10000])
    except Exception as e: return ToolResult(success=False,error=f"Read:{e}")

async def _query_codebase(a, ctx):
    try:
        from app.services.codegraph_service import get_codegraph_service
        r = get_codegraph_service().query_symbols(a.get("query",""))
        return ToolResult(success=True,data=r[:20] if isinstance(r,list) else [{"info":"done"}],content_type="json")
    except Exception as e:
        return ToolResult(success=True,data=[{"note":f"Unavailable:{str(e)[:80]}"}])

async def _write_file(a, ctx):
    """写入文件到项目目录"""
    import os
    path = a.get("path", "")
    content = a.get("content", "")
    if not path or not content:
        return ToolResult(success=False, error="缺少 path 或 content")

    # 安全限制：只允许写入 outputs 目录
    rp = os.path.realpath(path)
    prefixes = ["/root/Agent/backend/outputs", "e:\\桌面\\Agent\\backend\\outputs"]
    allowed = any(rp.startswith(os.path.realpath(pre)) for pre in prefixes if os.path.exists(os.path.realpath(pre) if pre.startswith("e:") else pre))
    # 如果没有任何已存在的允许路径，则允许写入 outputs 相对路径
    if not allowed and not path.startswith("outputs"):
        return ToolResult(success=False, error="只允许写入 outputs 目录")

    try:
        # 确保目录存在
        dir_path = os.path.dirname(rp) if os.path.isabs(path) else os.path.join("outputs", os.path.dirname(path))
        if not os.path.isabs(path):
            rp = os.path.join("outputs", path)
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        with open(rp, "w", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(success=True, data={"path": rp, "bytes": len(content)})
    except Exception as e:
        return ToolResult(success=False, error=str(e))

async def _analyze_code(a, ctx):
    """分析代码结构（提取函数、类、导入）"""
    import ast
    code = a.get("code", "")
    if not code:
        return ToolResult(success=False, error="缺少 code")

    try:
        tree = ast.parse(code)
        result = {
            "functions": [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)],
            "classes": [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)],
            "imports": [node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)],
            "import_froms": [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)],
            "total_lines": len(code.split("\n")),
        }
        return ToolResult(success=True, data=result, content_type="json")
    except SyntaxError as e:
        return ToolResult(success=False, error=f"语法错误: {str(e)[:100]}")
    except Exception as e:
        return ToolResult(success=False, error=f"解析失败: {str(e)[:100]}")

async def _list_files(a, ctx):
    """列出项目目录文件"""
    import os
    dir_path = a.get("directory", "outputs")
    if not os.path.exists(dir_path):
        dir_path = "outputs"
    try:
        files = []
        for root, dirs, filenames in os.walk(dir_path):
            for fn in filenames:
                fp = os.path.join(root, fn)
                try:
                    files.append({"path": fp, "size": os.path.getsize(fp)})
                except:
                    pass
        return ToolResult(success=True, data=files[:50], content_type="json")
    except Exception as e:
        return ToolResult(success=False, error=str(e))

def register_builtin_tools():
    ToolRegistry.register(ToolDef("web_search","Web search",{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]},_web_search,15,"search"))
    ToolRegistry.register(ToolDef("http_request","HTTP API calls",{"type":"object","properties":{"method":{"type":"string","enum":["GET","POST","PUT","DELETE"]},"url":{"type":"string"},"headers":{"type":"object"},"body":{"type":"object"}},"required":["method","url"]},_http_request,TOOL_TIMEOUT,"api"))
    ToolRegistry.register(ToolDef("run_python","Execute Python",{"type":"object","properties":{"code":{"type":"string"}},"required":["code"]},_run_python,30,"code"))
    ToolRegistry.register(ToolDef("read_project_file","Read files",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},_read_project_file,10,"file"))
    ToolRegistry.register(ToolDef("query_codebase","Search codebase",{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]},_query_codebase,15,"search"))
    # 新增工具
    ToolRegistry.register(ToolDef("write_file","写入文件",{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]},_write_file,10,"file"))
    ToolRegistry.register(ToolDef("analyze_code","分析代码结构",{"type":"object","properties":{"code":{"type":"string"}},"required":["code"]},_analyze_code,5,"code"))
    ToolRegistry.register(ToolDef("list_files","列出目录文件",{"type":"object","properties":{"directory":{"type":"string"}},"required":[]},_list_files,5,"file"))
    logger.info(f"Registered {len(ToolRegistry._tools)} tools")