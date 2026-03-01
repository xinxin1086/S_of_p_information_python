from flask import Blueprint

user_bp = Blueprint('user', __name__)

from . import auth
from . import profile

print("【API_user 用户端接口模块初始化完成】")