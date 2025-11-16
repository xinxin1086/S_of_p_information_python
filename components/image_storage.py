import os
import uuid
from datetime import datetime
from flask import current_app
from werkzeug.datastructures import FileStorage
from typing import Tuple, Dict, Optional


class LocalImageStorage:
    """本地图片存储工具类"""

    def __init__(self):
        # 从Flask配置中读取参数（需在app配置中预先定义）
        self.storage_dir = current_app.config.get(
            "IMAGE_STORAGE_DIR",  # 存储目录（默认：项目根目录下的images文件夹）
            os.path.join(current_app.root_path, "images")
        )
        self.allowed_extensions = current_app.config.get(
            "ALLOWED_IMAGE_EXTENSIONS",  # 允许的文件扩展名
            [".jpg", ".jpeg", ".png", ".gif", ".webp"]
        )
        self.allowed_mime_types = current_app.config.get(
            "ALLOWED_IMAGE_MIME_TYPES",  # 允许的MIME类型
            ["image/jpeg", "image/png", "image/gif", "image/webp"]
        )
        self.max_file_size = current_app.config.get(
            "MAX_IMAGE_SIZE",  # 最大文件大小（字节），默认5MB
            5 * 1024 * 1024  # 5MB
        )
        # 确保存储目录存在
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        """确保存储目录存在，不存在则创建"""
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)
            current_app.logger.info(f"创建图片存储目录：{self.storage_dir}")

    def _generate_unique_filename(self, original_filename: str) -> str:
        """生成唯一文件名（避免覆盖）"""
        # 提取原文件扩展名
        ext = os.path.splitext(original_filename)[1].lower()
        # 生成唯一标识：时间戳 + UUID
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = uuid.uuid4().hex[:8]  # 取UUID前8位
        return f"{timestamp}-{unique_id}{ext}"

    def _validate_file(self, file: FileStorage) -> Tuple[bool, str]:
        """验证文件合法性（类型、大小）"""
        # 检查文件是否为空
        if file.filename == "":
            return False, "未选择文件"

        # 检查文件大小
        if file.content_length > self.max_file_size:
            max_size_mb = self.max_file_size / 1024 / 1024
            return False, f"文件过大，最大支持{max_size_mb:.1f}MB"

        # 检查扩展名
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in self.allowed_extensions:
            allowed = ", ".join(self.allowed_extensions)
            return False, f"不支持的文件类型，允许：{allowed}"

        # 检查MIME类型
        if file.mimetype not in self.allowed_mime_types:
            allowed_mime = ", ".join(self.allowed_mime_types)
            return False, f"文件MIME类型不合法，允许：{allowed_mime}"

        return True, "验证通过"

    def save_image(self, file: FileStorage) -> Dict[str, Optional[str]]:
        """
        保存图片到本地存储

        参数：
            file: Flask接收的文件对象（werkzeug.datastructures.FileStorage）

        返回：
            成功：{"status": "success", "file_path": 本地存储路径, "url": 访问URL, "filename": 文件名}
            失败：{"status": "error", "message": 错误信息}
        """
        try:
            # 验证文件
            is_valid, msg = self._validate_file(file)
            if not is_valid:
                return {"status": "error", "message": msg}

            # 生成唯一文件名
            filename = self._generate_unique_filename(file.filename)
            # 完整存储路径
            file_path = os.path.join(self.storage_dir, filename)

            # 保存文件
            file.save(file_path)
            current_app.logger.info(f"图片保存成功：{file_path}")

            # 生成访问URL（需在Flask中配置静态路由映射存储目录）
            # 假设在app中配置了：app.static_url_path = "/images",app.static_folder = "images"
            image_url = f"/static/images/{filename}"

            return {
                "status": "success",
                "file_path": file_path,
                "url": image_url,
                "filename": filename
            }

        except Exception as e:
            current_app.logger.error(f"图片保存失败：{str(e)}")
            return {"status": "error", "message": f"保存失败：{str(e)}"}

    def delete_image(self, filename: str) -> Dict[str, str]:
        """删除本地图片（按文件名）"""
        try:
            file_path = os.path.join(self.storage_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                current_app.logger.info(f"图片删除成功：{file_path}")
                return {"status": "success", "message": "图片已删除"}
            else:
                return {"status": "error", "message": "图片不存在"}
        except Exception as e:
            current_app.logger.error(f"图片删除失败：{str(e)}")
            return {"status": "error", "message": f"删除失败：{str(e)}"}