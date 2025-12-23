# API_user 用户端接口模块初始化文件
from flask import Blueprint

# 创建用户端模块 Blueprint
user_bp = Blueprint('user', __name__, url_prefix='/user')

# 导入路由
from . import auth
from . import profile

print("【API_user 用户端接口模块初始化完成】")