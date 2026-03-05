# API_admin 模块初始化文件
# 管理员相关API模块

from API_admin.routes import (
    bp_admin,
    bp_admin_content,
    bp_admin_stats,
    super_admin_required,
    log_admin_operation,
    export_to_csv,
    validate_date_range,
    encrypt_sensitive_data,
    get_cross_module_pending_content,
    batch_update_user_display,
    check_system_security
)


def register_admin_blueprints(app):
    """
    注册所有管理员相关的蓝图

    Args:
        app: Flask应用实例
    """
    # 注册主蓝图
    app.register_blueprint(bp_admin)

    # 注册子蓝图
    app.register_blueprint(bp_admin_content)
    app.register_blueprint(bp_admin_stats)

    print("[成功] API_admin 所有蓝图注册完成")


# 导出所有蓝图和工具函数供其他模块使用
__all__ = [
    'bp_admin',
    'bp_admin_content',
    'bp_admin_stats',
    'register_admin_blueprints',
    'super_admin_required',
    'log_admin_operation',
    'export_to_csv',
    'validate_date_range',
    'encrypt_sensitive_data',
    'get_cross_module_pending_content',
    'batch_update_user_display',
    'check_system_security'
]
