from flask import Blueprint

admin_bp = Blueprint('user_admin', __name__, url_prefix='/admin')

from . import user_manage

print("【API_user 管理员端用户管理模块初始化完成】")