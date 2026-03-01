# API_user 认证授权模块初始化文件
from flask import Blueprint

# 创建认证模块 Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# 导入路由
from . import token

print("【API_user 认证授权模块初始化完成】")