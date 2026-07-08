"""文件服务 - 管理产出文件的存储和打包"""
import os
import zipfile
import aiofiles
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

OUTPUT_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "outputs")


class FileService:
    """文件管理服务"""

    def __init__(self):
        os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)

    def _get_task_dir(self, task_id: str) -> str:
        """获取任务目录路径"""
        task_dir = os.path.join(OUTPUT_BASE_DIR, task_id)
        os.makedirs(task_dir, exist_ok=True)
        return task_dir

    def _get_role_dir(self, task_id: str, role: str) -> str:
        """获取角色产出目录路径"""
        role_dir = os.path.join(self._get_task_dir(task_id), role)
        os.makedirs(role_dir, exist_ok=True)
        return role_dir

    async def save_file(self, role: str, filename: str, content: str, task_id: str = "current") -> str:
        """保存文件到角色产出目录"""
        role_dir = self._get_role_dir(task_id, role)
        filepath = os.path.join(role_dir, filename)

        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(content)

        logger.info(f"文件已保存: {filepath}")
        return filepath

    async def create_zip(self, task_id: str) -> str:
        """将任务的所有产出打包为ZIP文件"""
        task_dir = self._get_task_dir(task_id)
        zip_path = os.path.join(OUTPUT_BASE_DIR, f"{task_id}.zip")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(task_dir):
                for file in files:
                    if file.endswith(".zip"):
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, task_dir)
                    zf.write(file_path, arcname)

        logger.info(f"ZIP包已创建: {zip_path}")
        return zip_path

    def get_file_content(self, filepath: str) -> str:
        """读取文件内容"""
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def list_task_files(self, task_id: str) -> list:
        """列出任务的所有产出文件"""
        task_dir = self._get_task_dir(task_id)
        files = []
        for root, dirs, filenames in os.walk(task_dir):
            for f in filenames:
                filepath = os.path.join(root, f)
                relpath = os.path.relpath(filepath, task_dir)
                files.append({
                    "path": relpath,
                    "size": os.path.getsize(filepath),
                })
        return files
