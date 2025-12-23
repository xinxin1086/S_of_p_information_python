# API_science/__init__.py

"""
科普模块初始化文件
注册所有子模块的蓝图
"""

from .user import bp_science_user
from .admin import bp_science_admin
from .science import bp_science_category
from .science.public import bp_science_public

# 导入蓝图列表，便于主应用注册
__all__ = ['bp_science_user', 'bp_science_admin', 'bp_science_category', 'bp_science_public']

# 科普模块信息
MODULE_INFO = {
    'name': 'Science Module',
    'version': '1.0.0',
    'description': '科普文章管理模块，包含用户端、管理员端和公共接口',
    'blueprints': {
        'bp_science_user': '用户端科普操作接口',
        'bp_science_admin': '管理员科普管理接口',
        'bp_science_category': '科普业务公共接口',
        'bp_science_public': '科普文章公开访问接口'
    }
}