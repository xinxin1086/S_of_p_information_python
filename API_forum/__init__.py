# API_forum 初始化文件

from flask import Blueprint

def register_forum_blueprints(app):
    """注册论坛模块蓝图"""
    from .post import post_bp
    from .floor import floor_bp
    from .reply import reply_bp
    from .user import user_bp
    from .admin import admin_bp
    from .post.public import bp_forum_public

    # 注册所有蓝图
    app.register_blueprint(post_bp)
    app.register_blueprint(floor_bp)
    app.register_blueprint(reply_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(bp_forum_public)

    print("[成功] API_forum 所有蓝图注册完成")