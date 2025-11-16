from flask import Blueprint

# 创建公共蓝图，前缀为/api/common，供用户和管理员共用
common_bp = Blueprint('common', __name__, url_prefix='/api/common')

# 导入公共接口路由
from common import routes