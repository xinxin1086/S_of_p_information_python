# API_forum.floor 楼层模块初始化文件

from flask import Blueprint

# 创建楼层模块蓝图
floor_bp = Blueprint('floor', __name__, url_prefix='/api/forum/floors')

# 导入路由（必须在蓝图创建后导入）
from . import routes