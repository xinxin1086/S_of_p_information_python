# API_forum.admin 管理员模块初始化文件

from flask import Blueprint

# 创建管理员模块蓝图（使用唯一名称避免与 API_admin 冲突）
admin_bp = Blueprint('forum_admin', __name__, url_prefix='/api/forum/admin')

# 导入路由（必须在蓝图创建后导入）
from . import forum_manage