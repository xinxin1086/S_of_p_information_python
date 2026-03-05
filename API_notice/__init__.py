# API_notice 模块 - 优化后的统一入口
# 本模块提供所有公告相关的 API 接口

from flask import Blueprint, current_app
import logging

# 从 routes.py 导入所有 Blueprint
from .routes import (
    bp_notice_category,
    bp_notice_public,
    bp_notice_user,
    bp_notice_admin
)

logger = logging.getLogger(__name__)

# 创建主 Blueprint（可选，用于统一管理）
bp_notice_main = Blueprint('notice_main', __name__, url_prefix='/api/notice')

# 导出所有 Blueprint
__all__ = [
    'bp_notice_main',
    'bp_notice_category',
    'bp_notice_public',
    'bp_notice_user',
    'bp_notice_admin'
]


def register_blueprints(app):
    """
    注册所有公告相关的 Blueprint 到 Flask 应用

    Args:
        app: Flask 应用实例
    """
    app.register_blueprint(bp_notice_category)
    app.register_blueprint(bp_notice_public)
    app.register_blueprint(bp_notice_user)
    app.register_blueprint(bp_notice_admin)

    logger.info("【API_notice模块】所有 Blueprint 注册完成")


# 模块初始化日志
logger.info("【API_notice 模块加载完成】所有路由已统一至 routes.py")
