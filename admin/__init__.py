from flask import Blueprint

# 创建管理员蓝图（前缀为/api/admin）
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# 导入路由（确保蓝图注册后路由生效）
from admin import routes