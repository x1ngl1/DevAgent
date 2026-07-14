"""Leader Agent - 代码分析、测试任务规划与调度"""
import json
import asyncio
import logging
import ast
from typing import Dict, Any, List, Optional

from app.agents.base import AgentBase
from app.utils.prompt_templates import (
    LEADER_CODE_ANALYSIS_SYSTEM,
    LEADER_SUMMARIZE_SYSTEM,
    LEADER_CHECK_CONSENSUS_SYSTEM,
    LEADER_DISCUSS_SUMMARY_SYSTEM,
)

logger = logging.getLogger(__name__)


class LeaderAgent(AgentBase):
    """Leader Agent：分析代码结构、生成测试任务队列、汇总测试报告"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("leader", config)

    async def analyze_code_structure(self, code: str) -> Dict[str, Any]:
        """使用 AST 解析代码中的函数/类结构"""
        functions = []
        classes = []
        tree = None

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            logger.warning(f"代码解析失败: {e}")
            # 容错：还是让 LLM 分析
            pass

        if tree:
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # 解析函数签名
                    args = []
                    for arg in node.args.args:
                        args.append(arg.arg)
                    # 获取调用的函数
                    calls = []
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                            calls.append(child.func.id)
                        elif isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                            calls.append(f"{child.func.value.id}.{child.func.attr}" if isinstance(child.func.value, ast.Name) else child.func.attr)
                    docstring = ast.get_docstring(node) or ""
                    functions.append({
                        "name": node.name,
                        "args": args,
                        "calls": list(set(calls)),
                        "lineno": node.lineno,
                        "docstring": docstring[:200],
                    })
                elif isinstance(node, ast.ClassDef):
                    methods = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            methods.append(item.name)
                    classes.append({
                        "name": node.name,
                        "methods": methods,
                        "lineno": node.lineno,
                    })

        return {
            "functions": functions,
            "classes": classes,
            "function_count": len(functions),
            "class_count": len(classes),
        }

    async def build_dependency_graph(self, functions: List[Dict]) -> Dict[str, Any]:
        """构建函数调用依赖图，按被调用次数排序"""
        # 计算每个函数被调用的次数
        call_count = {}
        for func in functions:
            name = func["name"]
            if name not in call_count:
                call_count[name] = 0

        for func in functions:
            for called in func.get("calls", []):
                if called in call_count:
                    call_count[called] += 1

        # 按被调用次数排序（越多越核心）
        sorted_funcs = sorted(functions, key=lambda f: -call_count.get(f["name"], 0))

        # 构建依赖关系
        deps = {}
        for func in functions:
            name = func["name"]
            internal_calls = [c for c in func.get("calls", []) if c in call_count]
            deps[name] = internal_calls

        return {
            "sorted_functions": [f["name"] for f in sorted_funcs],
            "call_count": call_count,
            "dependencies": deps,
        }

    async def decompose(self, code_content: str, user_input: str = "") -> Dict:
        """分析代码内容并生成测试任务队列"""
        await self._update_status("running", {"phase": "analyze"})

        try:
            # Step 1: AST 解析
            ast_analysis = await self.analyze_code_structure(code_content)
            logger.info(f"AST 解析完成: {ast_analysis['function_count']} 个函数")

            # Step 2: 构建依赖图
            dep_graph = await self.build_dependency_graph(ast_analysis["functions"])
            logger.info(f"依赖图构建完成: {dep_graph['sorted_functions']}")

            # Step 3: LLM 深入分析
            prompt = f"""用户上传的代码文件内容：
```python
{code_content}
```

## AST 解析结果

函数列表：
{json.dumps(ast_analysis['functions'], ensure_ascii=False, indent=2)}

类列表：
{json.dumps(ast_analysis['classes'], ensure_ascii=False, indent=2)}

函数调用关系：
{json.dumps(dep_graph, ensure_ascii=False, indent=2)}

用户补充说明：{user_input if user_input else "无"}

请深入分析代码，识别每个函数的功能、输入输出、异常情况，然后按重要性生成测试任务列表。"""

            response = await self.chat(
                prompt=prompt,
                system_prompt=LEADER_CODE_ANALYSIS_SYSTEM,
            )
            result = self.parse_json_response(response)

            # 补充 AST 分析结果
            result["ast_analysis"] = {
                "function_count": ast_analysis["function_count"],
                "class_count": ast_analysis["class_count"],
                "dependency_graph": dep_graph,
            }

            subtasks = result.get("tasks", [])
            functions = result.get("functions", [])

            # 为每个函数构造测试子任务
            test_subtasks = []
            for task in subtasks:
                func_name = task.get("function_name", "")
                func_info = next((f for f in functions if f["name"] == func_name), {})
                deps = task.get("dependencies", [])
                test_subtasks.append({
                    "id": f"T{task.get('task_id', '001')}",
                    "role": "coder",
                    "description": f"为函数 {func_name} 编写单元测试\n函数签名: {func_info.get('signature', '')}\n函数描述: {func_info.get('description', '')}",
                    "depends_on": deps,
                    "function_name": func_name,
                    "priority": task.get("priority", 3),
                })

            # ── AST 兜底：LLM 未返回有效的测试任务时，用 AST 分析结果自动生成 ──
            if not test_subtasks and ast_analysis["function_count"] > 0:
                logger.info("LLM 未返回测试任务，使用 AST 兜底生成")
                for func in ast_analysis["functions"]:
                    name = func["name"]
                    priority = min(5, 1 + dep_graph["call_count"].get(name, 0))
                    deps = dep_graph["dependencies"].get(name, [])
                    test_subtasks.append({
                        "id": f"T{name.upper()[:4]}",
                        "role": "coder",
                        "description": f"为函数 {name} 编写单元测试\n函数参数: {func['args']}\n调用关系: {func.get('calls', [])}",
                        "depends_on": deps,
                        "function_name": name,
                        "priority": priority,
                    })
                # 补充 functions 信息供后续使用
                functions = [{"name": f["name"], "signature": f"def {f['name']}({', '.join(f['args'])}):", "args": f["args"], "calls": f.get("calls", [])} for f in ast_analysis["functions"]]

            # 添加 PM 审核和 Tester 执行任务
            test_subtasks.append({
                "id": "PM_FINAL",
                "role": "pm",
                "description": "审核所有测试代码质量并评估覆盖率",
                "depends_on": [t["id"] for t in test_subtasks],
            })
            test_subtasks.append({
                "id": "TEST_EXEC",
                "role": "tester",
                "description": "执行所有测试并收集覆盖率报告",
                "depends_on": [t["id"] for t in test_subtasks],
            })

            await self._update_status("done", {
                "phase": "analyze",
                "function_count": ast_analysis["function_count"],
                "task_count": len(test_subtasks),
                "tasks": test_subtasks,
                "code_summary": result.get("code_summary", ""),
            })

            return {
                "subtasks": test_subtasks,
                "summary": result.get("code_summary", f"分析了 {ast_analysis['function_count']} 个函数，生成 {len(test_subtasks)} 个测试任务"),
                "code_content": code_content,
                "functions": functions,
                "ast_analysis": ast_analysis,
                "dependency_graph": dep_graph,
            }

        except Exception as e:
            logger.error(f"Leader 分析失败: {e}")
            await self._update_status("error", {"error": str(e)})
            raise

    async def check_consensus(self, user_input: str, discussion_log: List[Dict]) -> Dict:
        """判断团队是否已达成共识"""
        try:
            response = await self.chat(
                prompt=f"用户需求：{user_input}\n\n讨论记录：\n{json.dumps(discussion_log, ensure_ascii=False, indent=2)}",
                system_prompt=LEADER_CHECK_CONSENSUS_SYSTEM,
            )
            return self.parse_json_response(response)
        except Exception as e:
            logger.warning(f"共识判断失败: {e}")
            return {"consensus": True, "remaining_concerns": ""}

    async def summarize_discussion(self, user_input: str, discussion_log: List[Dict], consensus: bool) -> Dict:
        """总结团队讨论"""
        try:
            status_text = "已达成共识" if consensus else "未完全达成共识，按多数意见执行"
            response = await self.chat(
                prompt=f"用户需求：{user_input}\n\n讨论记录：\n{json.dumps(discussion_log, ensure_ascii=False, indent=2)}\n\n讨论状态：{status_text}",
                system_prompt=LEADER_DISCUSS_SUMMARY_SYSTEM,
            )
            return self.parse_json_response(response)
        except Exception as e:
            logger.warning(f"讨论总结失败: {e}")
            return {"summary": "讨论结束，开始执行。"}

    async def generate_summary(
        self,
        user_input: str,
        code_content: str = "",
        coder_result: Dict = None,
        pm_result: Dict = None,
        tester_result: Dict = None,
        coverage_data: Dict = None,
        ast_analysis: Dict = None,
    ) -> str:
        """生成最终测试报告"""
        context = {
            "code_content": code_content[:500] if code_content else "",
            "coder": coder_result or {},
            "pm": pm_result or {},
            "tester": tester_result or {},
            "coverage": coverage_data or {},
            "ast_analysis": ast_analysis or {},
        }

        prompt = f"""## 被测代码摘要
{context['code_content'] if context['code_content'] else '无'}

## AST 分析结果
{json.dumps(context['ast_analysis'], ensure_ascii=False, indent=2) if context['ast_analysis'] else '无'}

## 测试执行结果
{json.dumps(context['coder'], ensure_ascii=False, indent=2) if context['coder'] else '无'}

## PM 审核结果
{json.dumps(context['pm'], ensure_ascii=False, indent=2) if context['pm'] else '无'}

## 测试执行详情
{json.dumps(context['tester'], ensure_ascii=False, indent=2) if context['tester'] else '无'}

## 覆盖率数据
{json.dumps(context['coverage'], ensure_ascii=False, indent=2) if context['coverage'] else '无'}

请生成给用户的最终测试报告。"""

        try:
            response = await self.chat(
                prompt=prompt,
                system_prompt=LEADER_SUMMARIZE_SYSTEM,
            )
            return response
        except Exception as e:
            logger.error(f"Leader 汇总失败: {e}")
            return f"测试完成！请查看测试报告。"
