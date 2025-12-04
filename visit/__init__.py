# ./visit/__init__.py

from flask import Blueprint

# 创建访客蓝图（前缀为/api/visit）
visit_bp = Blueprint('visit', __name__, url_prefix='/api/visit')

# 导入路由（确保蓝图注册后路由生效）
from visit import routes