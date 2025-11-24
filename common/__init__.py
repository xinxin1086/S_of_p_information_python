from flask import Blueprint
# 创建公共蓝图，前缀为/api/common，供其他蓝图调用，如用户蓝图等共用
common_bp = Blueprint('common', __name__, url_prefix='/api/common')

# 导入公共接口路由
from common import routes