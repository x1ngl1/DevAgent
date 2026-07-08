"""CodeGraph Skill - 代码分析技能

这是一个符合 Trae Skill 标准格式的实现，提供代码分析能力。
"""
import json
import subprocess
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

CODEGRAPH_PATH = "C:\\Users\\30126\\AppData\\Roaming\\npm\\node_modules\\@colbymchenry\\codegraph-win32-x64\\bin\\codegraph.cmd"


class CodeGraphSkill:
    """CodeGraph 代码分析技能"""

    SKILL_NAME = "codegraph"
    SKILL_DESCRIPTION = "代码分析与智能搜索技能，支持符号搜索、调用关系分析、影响范围评估等"
    
    def __init__(self):
        self._validate_installation()

    def _validate_installation(self) -> bool:
        """验证 CodeGraph 是否正确安装"""
        try:
            result = subprocess.run(
                [CODEGRAPH_PATH, "version"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                logger.info(f"CodeGraph version: {result.stdout.strip()}")
                return True
            else:
                logger.warning(f"CodeGraph validation failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"CodeGraph validation error: {e}")
            return False

    def _run_command(self, command: List[str], cwd: str = None) -> Optional[str]:
        """运行 CodeGraph 命令"""
        try:
            result = subprocess.run(
                [CODEGRAPH_PATH] + command,
                capture_output=True,
                text=True,
                cwd=cwd or "e:\\桌面\\Agent",
                timeout=60
            )
            if result.returncode == 0:
                return result.stdout
            else:
                logger.error(f"CodeGraph command failed: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            logger.error("CodeGraph command timed out")
            return None
        except Exception as e:
            logger.error(f"CodeGraph command error: {e}")
            return None

    def get_tools(self) -> List[Dict[str, Any]]:
        """返回技能支持的工具列表"""
        return [
            {
                "name": "codegraph_search",
                "description": "搜索代码库中的符号（函数、类、变量等）",
                "parameters": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                        "required": True
                    }
                }
            },
            {
                "name": "codegraph_explore",
                "description": "探索代码区域，获取相关符号和调用路径",
                "parameters": {
                    "query": {
                        "type": "string",
                        "description": "探索查询",
                        "required": True
                    }
                }
            },
            {
                "name": "codegraph_get_symbol_info",
                "description": "获取符号详细信息（源码、调用关系）",
                "parameters": {
                    "symbol": {
                        "type": "string",
                        "description": "符号名称",
                        "required": True
                    }
                }
            },
            {
                "name": "codegraph_get_callers",
                "description": "查找调用指定符号的函数",
                "parameters": {
                    "symbol": {
                        "type": "string",
                        "description": "符号名称",
                        "required": True
                    }
                }
            },
            {
                "name": "codegraph_get_callees",
                "description": "查找被指定符号调用的函数",
                "parameters": {
                    "symbol": {
                        "type": "string",
                        "description": "符号名称",
                        "required": True
                    }
                }
            },
            {
                "name": "codegraph_analyze_impact",
                "description": "分析代码变更的影响范围",
                "parameters": {
                    "symbol": {
                        "type": "string",
                        "description": "符号名称",
                        "required": True
                    }
                }
            },
            {
                "name": "codegraph_get_status",
                "description": "获取代码索引状态",
                "parameters": {}
            },
            {
                "name": "codegraph_get_files",
                "description": "获取项目文件列表",
                "parameters": {}
            }
        ]

    def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """调用指定的工具"""
        try:
            if tool_name == "codegraph_search":
                query = parameters.get("query", "")
                return {"result": self._search_symbols(query)}
            
            elif tool_name == "codegraph_explore":
                query = parameters.get("query", "")
                return {"result": self._explore_code(query)}
            
            elif tool_name == "codegraph_get_symbol_info":
                symbol = parameters.get("symbol", "")
                return {"result": self._get_symbol_info(symbol)}
            
            elif tool_name == "codegraph_get_callers":
                symbol = parameters.get("symbol", "")
                return {"result": self._get_callers(symbol)}
            
            elif tool_name == "codegraph_get_callees":
                symbol = parameters.get("symbol", "")
                return {"result": self._get_callees(symbol)}
            
            elif tool_name == "codegraph_analyze_impact":
                symbol = parameters.get("symbol", "")
                return {"result": self._analyze_impact(symbol)}
            
            elif tool_name == "codegraph_get_status":
                return {"result": self._get_status()}
            
            elif tool_name == "codegraph_get_files":
                return {"result": self._get_files()}
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Tool call error: {e}")
            return {"error": str(e)}

    def _search_symbols(self, query: str) -> Dict[str, Any]:
        """搜索符号"""
        output = self._run_command(["query", query])
        if not output:
            return {"error": "Failed to search"}
        
        lines = output.strip().split("\n")
        results = []
        for line in lines:
            if line.strip() and not line.startswith("Search Results"):
                parts = line.split("  ", 1)
                if len(parts) >= 2:
                    kind_info = parts[0].strip()
                    rest = parts[1].strip()
                    # 解析类型和名称
                    if "%" in kind_info:
                        kind_part, score_part = kind_info.rsplit(" ", 1)
                        kind = kind_part.strip()
                        score = score_part.replace("(", "").replace(")", "")
                    else:
                        kind = kind_info
                        score = "0%"
                    
                    # 解析位置
                    if rest:
                        if "(" in rest:
                            name_end = rest.find("(")
                            name = rest[:name_end].strip()
                            rest = rest[name_end:]
                        else:
                            # 查找文件路径
                            path_start = rest.find("backend/")
                            if path_start != -1:
                                name = rest[:path_start].strip()
                                filepath = rest[path_start:].strip()
                            else:
                                name = rest
                                filepath = ""
                    results.append({
                        "kind": kind,
                        "name": name,
                        "score": score,
                        "location": filepath if 'filepath' in dir() else rest
                    })
        return {"query": query, "results": results}

    def _explore_code(self, query: str) -> Dict[str, Any]:
        """探索代码区域"""
        output = self._run_command(["explore", query])
        if not output:
            return {"error": "Failed to explore"}
        
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"output": output}

    def _get_symbol_info(self, symbol_name: str) -> Dict[str, Any]:
        """获取符号详细信息"""
        output = self._run_command(["node", symbol_name])
        if not output:
            return {"error": "Failed to get symbol info"}
        
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"output": output}

    def _get_callers(self, symbol_name: str) -> List[str]:
        """获取调用者"""
        output = self._run_command(["callers", symbol_name])
        if not output:
            return []
        return [line.strip() for line in output.strip().split("\n") if line.strip()]

    def _get_callees(self, symbol_name: str) -> List[str]:
        """获取被调用者"""
        output = self._run_command(["callees", symbol_name])
        if not output:
            return []
        return [line.strip() for line in output.strip().split("\n") if line.strip()]

    def _analyze_impact(self, symbol_name: str) -> Dict[str, Any]:
        """分析变更影响"""
        output = self._run_command(["impact", symbol_name])
        if not output:
            return {"error": "Failed to analyze impact"}
        
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"output": output}

    def _get_status(self) -> Dict[str, Any]:
        """获取状态"""
        output = self._run_command(["status"])
        if not output:
            return {"error": "Failed to get status"}
        
        result = {}
        lines = output.strip().split("\n")
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        return result

    def _get_files(self) -> List[str]:
        """获取文件列表"""
        output = self._run_command(["files"])
        if not output:
            return []
        return [line.strip() for line in output.strip().split("\n") if line.strip()]


# 全局技能实例
_codegraph_skill = None


def get_codegraph_skill() -> CodeGraphSkill:
    """获取 CodeGraph 技能实例"""
    global _codegraph_skill
    if _codegraph_skill is None:
        _codegraph_skill = CodeGraphSkill()
    return _codegraph_skill


# Trae Skill 标准接口
def initialize():
    """初始化技能"""
    return get_codegraph_skill()


def get_skill_info() -> Dict[str, Any]:
    """获取技能信息"""
    skill = get_codegraph_skill()
    return {
        "name": skill.SKILL_NAME,
        "description": skill.SKILL_DESCRIPTION,
        "tools": skill.get_tools()
    }


def execute_tool(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """执行工具"""
    skill = get_codegraph_skill()
    return skill.call_tool(tool_name, parameters)