# API_forum.user 用户模块初始化文件

from flask import Blueprint

# 创建用户模块蓝图（使用唯一名称避免与其他 user 模块冲突）
user_bp = Blueprint('forum_user', __name__, url_prefix='/api/forum/users')

# 导入路由（必须在蓝图创建后导入）
from . import user_ops