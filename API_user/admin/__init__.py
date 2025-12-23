# API_user 管理员端用户管理模块初始化文件
from flask import Blueprint

# 创建管理员用户管理模块 Blueprint（使用唯一名称避免与其他 admin 模块冲突）
admin_bp = Blueprint('user_admin', __name__, url_prefix='/admin')

# 导入路由
from . import user_manage

print("【API_user 管理员端用户管理模块初始化完成】")