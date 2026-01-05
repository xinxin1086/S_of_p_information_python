# API_user 用户端接口模块初始化文件
from flask import Blueprint

# 创建用户端模块 Blueprint（无前缀，让子模块自己定义）
user_bp = Blueprint('user', __name__)

# 导入路由
from . import auth
from . import profile

print("【API_user 用户端接口模块初始化完成】")