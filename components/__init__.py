from components.models import db
from components.utils import token_required

# 导出公共对象供其他模块使用
__all__ = ['db', 'token_required']