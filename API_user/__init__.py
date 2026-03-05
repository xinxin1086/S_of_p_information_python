# API_user 模块初始化文件
# 简化版：统一路由结构

from .routes import (
    api_user_bp,
    user_bp,
    admin_bp,
    auth_bp,
    bp_user_public
)

__all__ = ['api_user_bp', 'user_bp', 'admin_bp', 'auth_bp', 'bp_user_public']

print("【API_user 模块初始化完成】已加载统一路由结构")
