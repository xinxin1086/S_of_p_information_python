# ./app.py
"""
Flask 应用入口
采用工厂模式，确保测试能导入 create_app
"""

from flask import Flask
import os
from flask_cors import CORS
from flask import send_from_directory
from config import Config
from components import db  # 引用公共数据库

# 导入所有蓝图和注册函数
from API_admin import register_admin_blueprints  # 导入重构后的管理员模块
from API_user import api_user_bp, bp_user_public  # 导入重构后的用户模块
from common import common_bp  # 导入公共蓝图
from API_science import bp_science_public
from API_forum import register_forum_blueprints
from API_notice import register_blueprints as register_notice_blueprints
from API_activities import register_api_activities_blueprints


def create_app(config_object=None):
    """
    Flask 应用工厂函数（测试用例核心依赖）
    :param config_object: 配置对象，可以是类或实例
    :return: Flask app 实例
    """
    # 初始化 app
    app = Flask(__name__)

    # 使用默认配置（如果没有提供配置对象）
    if config_object is None:
        config_object = Config

    # 如果是配置类，则实例化
    if isinstance(config_object, type):
        config_object = config_object()

    # 应用配置
    app.config.from_object(config_object)

    # 配置CORS（允许跨域）
    CORS(app, resources={
        r"/api/*": {
            "origins": ["https://testagent.xspaceagi.com", "http://localhost:3000", "http://127.0.0.1:3000"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })

    # 初始化数据库
    db.init_app(app)

    # 注册主要蓝图
    app.register_blueprint(api_user_bp)   # 重构后的用户接口
    app.register_blueprint(common_bp)     # 公共接口

    # 注册公开访问接口蓝图
    app.register_blueprint(bp_science_public)  # 科普文章公开访问
    app.register_blueprint(bp_user_public)     # 用户信息公开访问

    # 注册子模块蓝图（包含其他公开访问接口）
    register_admin_blueprints(app)        # 管理员子模块
    register_forum_blueprints(app)        # 论坛模块（包含公开访问接口）
    register_notice_blueprints(app)       # 公告模块（包含公开访问接口）
    register_api_activities_blueprints(app) # 活动模块（包含用户端、管理端、预约、讨论等）

    # 图片静态路由
    @app.route('/static/images/<filename>')
    def serve_image(filename):
        image_dir = app.config.get('IMAGE_STORAGE_DIR', 'static/images')
        return send_from_directory(os.path.abspath(image_dir), filename)

    # 输出模块加载信息（保持原有日志输出）
    print("【API_user 公共工具模块加载完成】")
    print("【API_user 用户端认证接口模块加载完成】")
    print("【API_user 用户端个人信息接口模块加载完成】")
    print("【API_user 用户端接口模块初始化完成】")
    print("【API_user 管理员用户管理接口模块加载完成】")
    print("【API_user 管理员端用户管理模块初始化完成】")
    print("【API_user 认证授权接口模块加载完成】")
    print("【API_user 认证授权模块初始化完成】")
    print("【API_user 公开访问接口模块加载完成】")
    print("【API_user 模块初始化完成】已注册所有子模块 Blueprint")
    print("【API_science 公开访问接口模块加载完成】")
    print("【API_notice 公开访问接口模块加载完成】")
    print("[成功] API_admin 所有蓝图注册完成")
    print("【API_forum 公开访问接口模块加载完成】")
    print("[成功] API_forum 所有蓝图注册完成")
    print("【API_notice模块】所有Blueprint注册完成")
    print("【API_activities模块】所有蓝图注册完成")
    print("  - 用户操作模块: /api/activities/user/*")
    print("  - 管理员模块: /api/activities/admin/*")
    print("  - 预约模块: /api/activities/booking/*")
    print("  - 讨论模块: /api/activities/discussion/*")


    # 初始化数据库表和测试数据
    with app.app_context():
        db.create_all()
        print("数据库表创建成功！")

        from components.models import Admin  # 局部导入避免循环引用
        # 添加测试管理员（若不存在）
        if not db.session.query(db.exists().where(Admin.account == 'admin')).scalar():
            admin_data = {
                'account': 'admin',
                'username': '超级管理员',
                'phone': '13800138000',
                'email': 'admin@example.com',
                'role': 'SUPER_ADMIN'
            }
            test_admin = Admin.create_with_user(admin_data, '123456')  # 密码：123456
            print("【初始化】测试管理员创建成功")

    # 必须返回 app 实例
    return app


# ========== 非测试环境执行入口（仅直接运行 app.py 时生效） ==========
if __name__ == '__main__':
    # 创建 app 实例
    app = create_app()

    # 运行应用
    app.run(debug=True, host='0.0.0.0', port=5000)


