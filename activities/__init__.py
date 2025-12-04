# ./activities/__init__.py

from flask import Blueprint

# 创建activities蓝图，URL前缀为 /api/activities
activities_bp = Blueprint('activities', __name__, url_prefix='/api/activities')

# 导入路由（避免循环依赖）
from . import routes