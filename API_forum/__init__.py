
from flask import Blueprint

def register_forum_blueprints(app):
    
    from .post import post_bp
    from .floor import floor_bp
    from .reply import reply_bp
    from .user import user_bp
    from .admin import admin_bp
    from .post.public import bp_forum_public

    app.register_blueprint(post_bp)
    app.register_blueprint(floor_bp)
    app.register_blueprint(reply_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(bp_forum_public)

    print("[成功] API_forum 所有蓝图注册完成")