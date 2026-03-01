
from flask import Blueprint

api_user_bp = Blueprint('api_user', __name__, url_prefix='/api/user')

from .user import user_bp
from .admin import admin_bp
from .auth import auth_bp
from .user.public import bp_user_public

api_user_bp.register_blueprint(user_bp)
api_user_bp.register_blueprint(admin_bp)
api_user_bp.register_blueprint(auth_bp)

__all__ = ['api_user_bp', 'user_bp', 'admin_bp', 'auth_bp', 'bp_user_public']

print("【API_user 模块初始化完成】已注册所有子模块 Blueprint")