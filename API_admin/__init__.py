# API_admin 模块初始化文件

from flask import Blueprint
from API_admin.content.content_audit import bp_admin_content
from API_admin.statistics.stats import bp_admin_stats

# 创建主管理员蓝图
bp_admin = Blueprint('admin', __name__, url_prefix='/api/admin')

# 注册子蓝图
def register_admin_blueprints(app):
    """
    注册所有管理员相关的蓝图

    Args:
        app: Flask应用实例
    """
    # 确保管理员管理接口已加载
    from API_admin import admin_manage  # noqa: F401

    # 注册主蓝图
    app.register_blueprint(bp_admin)

    # 注册子蓝图
    app.register_blueprint(bp_admin_content)
    app.register_blueprint(bp_admin_stats)

    print("[成功] API_admin 所有蓝图注册完成")

# 导出主蓝图供其他模块使用
__all__ = ['bp_admin', 'register_admin_blueprints']
