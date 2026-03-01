from flask import Blueprint

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

from . import token

print("【API_user 认证授权模块初始化完成】")