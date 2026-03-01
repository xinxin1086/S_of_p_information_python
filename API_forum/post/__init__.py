# API_forum.post 帖子模块初始化文件

from flask import Blueprint

# 创建帖子模块蓝图
post_bp = Blueprint('post', __name__, url_prefix='/api/forum/posts')

# 导入路由（必须在蓝图创建后导入）
from . import routes
from . import public