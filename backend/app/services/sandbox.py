"""Docker沙箱服务 - 安全执行代码 (支持子进程回退)"""
import asyncio
import logging
import tempfile
import os
import subprocess
from typing import Dict

from app.config import SANDBOX_PYTHON_IMAGE

logger = logging.getLogger(__name__)


class SandboxService:
    """Docker沙箱服务，在隔离环境中执行测试（Docker不可用时自动回退到本地子进程）"""

    def __init__(self):
        self.image = SANDBOX_PYTHON_IMAGE

    async def run_tests(self, files: Dict[str, str]) -> Dict:
        """在沙箱中执行测试，Docker不可用时回退到本地子进程"""
        try:
            return await self._run_docker(files)
        except Exception as e:
            logger.warning(f"Docker 沙箱不可用 ({e})，回退到本地子进程执行")
            try:
                return await self._run_local(files)
            except Exception as e2:
                logger.error(f"本地测试执行也失败: {e2}")
                return {
                    "success": False,
                    "exit_code": -1,
                    "output": f"测试执行失败: Docker不可用({e})，本地执行也失败({e2})",
                    "coverage": 0.0,
                }

    async def _run_docker(self, files: Dict[str, str]) -> Dict:
        """通过 Docker 执行测试"""
        import docker
        client = await asyncio.to_thread(docker.from_env)

        with tempfile.TemporaryDirectory(prefix="sandbox_") as tmpdir:
            for filename, content in files.items():
                filepath = os.path.join(tmpdir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

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
                result = await asyncio.to_thread(container.wait, timeout=30)
                logs = await asyncio.to_thread(
                    lambda: container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
                )
                await asyncio.to_thread(container.remove)

                coverage = self._parse_coverage(logs)

                return {
                    "success": result["StatusCode"] == 0,
                    "exit_code": result["StatusCode"],
                    "output": logs,
                    "coverage": coverage,
                }
            except docker.errors.ContainerError as e:
                return {"success": False, "error": str(e), "coverage": 0.0}

    async def _run_local(self, files: Dict[str, str]) -> Dict:
        """通过本地子进程执行测试（Docker不可用时的回退方案）"""
        with tempfile.TemporaryDirectory(prefix="test_local_") as tmpdir:
            # 写入所有文件
            for filename, content in files.items():
                filepath = os.path.join(tmpdir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

            test_cmd = "pytest test_*.py -v --cov=. --cov-report=term --cov-report=html 2>&1 || true"

            try:
                proc = await asyncio.create_subprocess_shell(
                    test_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=tmpdir,
                )
                try:
                    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
                except asyncio.TimeoutError:
                    proc.kill()
                    stdout, _ = await proc.communicate()
                    output = (stdout or b"").decode("utf-8", errors="replace")
                    output += "\n\n[测试执行超时]"
                    return {
                        "success": False,
                        "exit_code": -1,
                        "output": output,
                        "coverage": 0.0,
                    }

                output = stdout.decode("utf-8", errors="replace") if stdout else ""
                exit_code = proc.returncode or 0
                coverage = self._parse_coverage(output)

                return {
                    "success": exit_code == 0,
                    "exit_code": exit_code,
                    "output": output,
                    "coverage": coverage,
                }
            except FileNotFoundError:
                logger.error("pytest 未安装，无法执行本地测试")
                return {
                    "success": False,
                    "exit_code": -1,
                    "output": "pytest 未安装，请运行: pip install pytest pytest-cov",
                    "coverage": 0.0,
                }

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
