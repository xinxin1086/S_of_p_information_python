
from flask import Blueprint
from API_admin.content.content_audit import bp_admin_content
from API_admin.statistics.stats import bp_admin_stats

bp_admin = Blueprint('admin', __name__, url_prefix='/api/admin')

def register_admin_blueprints(app):
    
    from API_admin import admin_manage

    app.register_blueprint(bp_admin)

    app.register_blueprint(bp_admin_content)
    app.register_blueprint(bp_admin_stats)

    print("[成功] API_admin 所有蓝图注册完成")

__all__ = ['bp_admin', 'register_admin_blueprints']
