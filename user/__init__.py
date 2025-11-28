# ./user/__init__.py

from flask import Blueprint

# 创建用户蓝图（前缀为/api/user）
user_bp = Blueprint('user', __name__, url_prefix='/api/user')

# 导入路由（预留）
from user import routes