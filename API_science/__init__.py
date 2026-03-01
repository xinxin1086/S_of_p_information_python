

from .user import bp_science_user
from .admin import bp_science_admin
from .science import bp_science_category
from .science.public import bp_science_public

__all__ = ['bp_science_user', 'bp_science_admin', 'bp_science_category', 'bp_science_public']

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


def register_science_blueprints(app):
    
    app.register_blueprint(bp_science_user)
    app.register_blueprint(bp_science_admin)
    app.register_blueprint(bp_science_category)
    app.register_blueprint(bp_science_public)

    print("【API_science模块】所有蓝图注册完成")
    print("  - 用户端科普操作: /api/science/user/*")
    print("  - 管理员科普管理: /api/science/admin/*")
    print("  - 科普业务公共接口: /api/science/category/*")
    print("  - 科普文章公开访问: /api/public/science/*")