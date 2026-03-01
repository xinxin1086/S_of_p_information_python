
import os
import uuid
from datetime import datetime
from flask import current_app
from werkzeug.datastructures import FileStorage
from typing import Tuple, Dict, Optional


class LocalImageStorage:
    

    def __init__(self):
        self.storage_dir = current_app.config.get(
            "IMAGE_STORAGE_DIR",
            os.path.join(current_app.root_path, "images")
        )
        self.allowed_extensions = current_app.config.get(
            "ALLOWED_IMAGE_EXTENSIONS",
            [".jpg", ".jpeg", ".png", ".gif", ".webp"]
        )
        self.allowed_mime_types = current_app.config.get(
            "ALLOWED_IMAGE_MIME_TYPES",
            ["image/jpeg", "image/png", "image/gif", "image/webp"]
        )
        self.max_file_size = current_app.config.get(
            "MAX_IMAGE_SIZE",
            5 * 1024 * 1024
        )
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)
            current_app.logger.info(f"创建图片存储目录：{self.storage_dir}")

    def _generate_unique_filename(self, original_filename: str) -> str:
        
        ext = os.path.splitext(original_filename)[1].lower()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"{timestamp}-{unique_id}{ext}"

    def _validate_file(self, file: FileStorage) -> Tuple[bool, str]:
        
        if file.filename == "":
            return False, "未选择文件"

        if file.content_length > self.max_file_size:
            max_size_mb = self.max_file_size / 1024 / 1024
            return False, f"文件过大，最大支持{max_size_mb:.1f}MB"

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in self.allowed_extensions:
            allowed = ", ".join(self.allowed_extensions)
            return False, f"不支持的文件类型，允许：{allowed}"

        if file.mimetype not in self.allowed_mime_types:
            allowed_mime = ", ".join(self.allowed_mime_types)
            return False, f"文件MIME类型不合法，允许：{allowed_mime}"

        return True, "验证通过"

    def save_image(self, file: FileStorage) -> Dict[str, Optional[str]]:
        
        try:
            is_valid, msg = self._validate_file(file)
            if not is_valid:
                return {"status": "error", "message": msg}

            filename = self._generate_unique_filename(file.filename)
            file_path = os.path.join(self.storage_dir, filename)

            file.save(file_path)
            current_app.logger.info(f"图片保存成功：{file_path}")

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