# API_user 模块初始化文件
# 统一注册所有子模块的 Blueprint

from flask import Blueprint

# 创建主 Blueprint
api_user_bp = Blueprint('api_user', __name__, url_prefix='/api/user')

# 导入并注册子模块 Blueprint
from .user import user_bp
from .admin import admin_bp
from .auth import auth_bp
from .user.public import bp_user_public

# 注册子模块到主模块
api_user_bp.register_blueprint(user_bp)
api_user_bp.register_blueprint(admin_bp)
api_user_bp.register_blueprint(auth_bp)

# 导出公开访问蓝图供主应用直接注册
__all__ = ['api_user_bp', 'user_bp', 'admin_bp', 'auth_bp', 'bp_user_public']

print("【API_user 模块初始化完成】已注册所有子模块 Blueprint")