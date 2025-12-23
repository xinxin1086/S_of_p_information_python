# API_notice模块主初始化文件
# 注册所有公告相关的Blueprint

from flask import Blueprint
from .user import bp_notice_user
from .admin import bp_notice_admin
from .notice import bp_notice_category
from .notice.public import bp_notice_public

# 创建主Blueprint
bp_notice_main = Blueprint('notice_main', __name__, url_prefix='/api/notice')

# 导出所有Blueprint
__all__ = [
    'bp_notice_main',
    'bp_notice_user',
    'bp_notice_admin',
    'bp_notice_category',
    'bp_notice_public'
]

# 注册函数
def register_blueprints(app):
    """
    注册所有公告相关的Blueprint到Flask应用

    Args:
        app: Flask应用实例
    """
    app.register_blueprint(bp_notice_user)
    app.register_blueprint(bp_notice_admin)
    app.register_blueprint(bp_notice_category)
    app.register_blueprint(bp_notice_public)

    print("【API_notice模块】所有Blueprint注册完成")