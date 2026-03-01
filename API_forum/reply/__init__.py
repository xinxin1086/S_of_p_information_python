# API_forum.reply 回复模块初始化文件

from flask import Blueprint

# 创建回复模块蓝图
reply_bp = Blueprint('reply', __name__, url_prefix='/api/forum/replies')

# 导入路由（必须在蓝图创建后导入）
from . import routes