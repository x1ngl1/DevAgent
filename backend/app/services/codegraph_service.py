"""CodeGraph 服务 - 提供代码分析能力"""
import json
import subprocess
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

CODEGRAPH_PATH = "C:\\Users\\30126\\AppData\\Roaming\\npm\\node_modules\\@colbymchenry\\codegraph-win32-x64\\bin\\codegraph.cmd"


class CodeGraphService:
    """CodeGraph 代码分析服务"""

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

    def get_status(self) -> Dict[str, Any]:
        """获取 CodeGraph 状态"""
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

    def query_symbols(self, search_query: str) -> List[Dict[str, Any]]:
        """搜索符号"""
        output = self._run_command(["query", search_query])
        if not output:
            return []
        
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse query result: {output}")
            return []

    def explore_code(self, query: str) -> Dict[str, Any]:
        """探索代码区域"""
        output = self._run_command(["explore", query])
        if not output:
            return {"error": "Failed to explore"}
        
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            # 如果不是 JSON，返回原始输出
            return {"output": output}

    def get_symbol_info(self, symbol_name: str) -> Dict[str, Any]:
        """获取符号详细信息"""
        output = self._run_command(["node", symbol_name])
        if not output:
            return {"error": "Failed to get symbol info"}
        
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"output": output}

    def get_callers(self, symbol_name: str) -> List[str]:
        """获取调用者"""
        output = self._run_command(["callers", symbol_name])
        if not output:
            return []
        return [line.strip() for line in output.strip().split("\n") if line.strip()]

    def get_callees(self, symbol_name: str) -> List[str]:
        """获取被调用者"""
        output = self._run_command(["callees", symbol_name])
        if not output:
            return []
        return [line.strip() for line in output.strip().split("\n") if line.strip()]

    def analyze_impact(self, symbol_name: str) -> Dict[str, Any]:
        """分析变更影响"""
        output = self._run_command(["impact", symbol_name])
        if not output:
            return {"error": "Failed to analyze impact"}
        
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"output": output}

    def get_files(self) -> List[str]:
        """获取项目文件列表"""
        output = self._run_command(["files"])
        if not output:
            return []
        return [line.strip() for line in output.strip().split("\n") if line.strip()]

    def reindex(self) -> bool:
        """重新索引项目"""
        output = self._run_command(["index"])
        return output is not None


# 单例实例
_codegraph_service = None


def get_codegraph_service() -> CodeGraphService:
    """获取 CodeGraph 服务实例"""
    global _codegraph_service
    if _codegraph_service is None:
        _codegraph_service = CodeGraphService()
    return _codegraph_service