# API_forum 初始化文件

from flask import Blueprint

# 从统一的 routes.py 导入所有蓝图
from .routes import (
    post_bp,          # 帖子路由
    floor_bp,         # 楼层路由
    reply_bp,         # 回复路由
    user_bp,          # 用户操作路由
    admin_bp,         # 管理员路由
    bp_forum_public   # 公开访问路由
)


def register_forum_blueprints(app):
    """注册论坛模块蓝图"""
    # 注册所有蓝图
    app.register_blueprint(post_bp)
    app.register_blueprint(floor_bp)
    app.register_blueprint(reply_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(bp_forum_public)

    print("[成功] API_forum 所有蓝图注册完成")
