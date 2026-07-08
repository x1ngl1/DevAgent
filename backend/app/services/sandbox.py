"""Docker沙箱服务 - 安全执行代码"""
import asyncio
import logging
import tempfile
import os
from typing import Dict

from app.config import SANDBOX_PYTHON_IMAGE

logger = logging.getLogger(__name__)


class SandboxService:
    """Docker沙箱服务，在隔离环境中执行代码"""

    def __init__(self):
        self.image = SANDBOX_PYTHON_IMAGE

    async def run_tests(self, files: Dict[str, str]) -> Dict:
        """在沙箱中执行测试"""
        try:
            import docker
            client = await asyncio.to_thread(docker.from_env)
        except Exception as e:
            logger.warning(f"Docker不可用: {e}")
            raise RuntimeError(f"Docker服务不可用: {e}")

        # 创建临时目录存放代码
        with tempfile.TemporaryDirectory(prefix="sandbox_") as tmpdir:
            # 写入所有文件
            for filename, content in files.items():
                filepath = os.path.join(tmpdir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

            # 查找测试命令
            test_cmd = "pytest test_*.py -v --cov=. --cov-report=term --cov-report=html 2>&1 || true"

            try:
                container = await asyncio.to_thread(
                    client.containers.run,
                    image=self.image,
                    command=f"sh -c 'cd /workspace && {test_cmd}'",
                    volumes={tmpdir: {"bind": "/workspace", "mode": "rw"}},
                    mem_limit="512m",
                    cpu_period=100000,
                    cpu_quota=50000,
                    detach=True,
                    remove=False,
                )

                # 等待完成（超时30秒）
                result = await asyncio.to_thread(container.wait, timeout=30)
                logs = await asyncio.to_thread(
                    lambda: container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
                )
                await asyncio.to_thread(container.remove)

                # 提取覆盖率
                coverage = self._parse_coverage(logs)

                return {
                    "success": result["StatusCode"] == 0,
                    "exit_code": result["StatusCode"],
                    "output": logs,
                    "coverage": coverage,
                }

            except docker.errors.ContainerError as e:
                return {"success": False, "error": str(e), "coverage": 0.0}
            except Exception as e:
                logger.error(f"沙箱执行异常: {e}")
                return {"success": False, "error": str(e), "coverage": 0.0}

    def _parse_coverage(self, logs: str) -> float:
        """从pytest输出中解析覆盖率"""
        import re
        # 匹配类似 "TOTAL          12      2    83%"
        match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", logs)
        if match:
            return int(match.group(1)) / 100.0
        return 0.0

    async def run_code(self, code: str, language: str = "Python") -> Dict:
        """在沙箱中执行代码片段"""
        try:
            import docker
            client = await asyncio.to_thread(docker.from_env)
        except Exception as e:
            raise RuntimeError(f"Docker服务不可用: {e}")

        with tempfile.TemporaryDirectory(prefix="sandbox_") as tmpdir:
            filepath = os.path.join(tmpdir, "script.py")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)

            try:
                container = await asyncio.to_thread(
                    client.containers.run,
                    image=self.image,
                    command="python /workspace/script.py",
                    volumes={tmpdir: {"bind": "/workspace", "mode": "rw"}},
                    mem_limit="512m",
                    cpu_period=100000,
                    cpu_quota=50000,
                    detach=True,
                    remove=False,
                )
                result = await asyncio.to_thread(container.wait, timeout=30)
                logs = await asyncio.to_thread(
                    lambda: container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
                )
                await asyncio.to_thread(container.remove)

                return {
                    "success": result["StatusCode"] == 0,
                    "exit_code": result["StatusCode"],
                    "output": logs,
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
