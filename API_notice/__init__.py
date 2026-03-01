
from flask import Blueprint
import logging
from .user import bp_notice_user
from .admin import bp_notice_admin
from .notice import bp_notice_category
from .notice.public import bp_notice_public

bp_notice_main = Blueprint('notice_main', __name__, url_prefix='/api/notice')

logger = logging.getLogger(__name__)

__all__ = [
    'bp_notice_main',
    'bp_notice_user',
    'bp_notice_admin',
    'bp_notice_category',
    'bp_notice_public'
]

def register_blueprints(app):
    
    app.register_blueprint(bp_notice_user)
    app.register_blueprint(bp_notice_admin)
    app.register_blueprint(bp_notice_category)
    app.register_blueprint(bp_notice_public)

    logger.info("【API_notice模块】所有Blueprint注册完成")