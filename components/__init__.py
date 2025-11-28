# ./components/__init__.py

from components.models import db
from components.token_required import token_required
from components.image_storage import LocalImageStorage

# 导出公共对象供其他模块使用
__all__ = ['db', 'token_required', 'LocalImageStorage']