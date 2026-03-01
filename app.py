

from flask import Flask
import os
from flask_cors import CORS
from flask import send_from_directory
from config import Config
from components import db

from API_admin import register_admin_blueprints
from API_user import api_user_bp, bp_user_public
from common import common_bp
from common.compat import compat_bp
from API_science import register_science_blueprints
from API_forum import register_forum_blueprints
from API_notice import register_blueprints as register_notice_blueprints
from API_activities import register_api_activities_blueprints


def create_app(config_object=None):
    
    app = Flask(__name__)

    if config_object is None:
        config_object = Config

    if isinstance(config_object, type):
        config_object = config_object()

    app.config.from_object(config_object)

    CORS(app, resources={
        r"/api/*": {
            "origins": ["https://testagent.xspaceagi.com", "http://localhost:3000", "http://127.0.0.1:3000"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })

    db.init_app(app)

    app.register_blueprint(api_user_bp)
    app.register_blueprint(common_bp)
    app.register_blueprint(compat_bp)

    app.register_blueprint(bp_user_public)

    register_admin_blueprints(app)
    register_science_blueprints(app)
    register_forum_blueprints(app)
    register_notice_blueprints(app)
    register_api_activities_blueprints(app)

    @app.route('/static/images/<filename>')
    def serve_image(filename):
        image_dir = app.config.get('IMAGE_STORAGE_DIR', 'static/images')
        return send_from_directory(os.path.abspath(image_dir), filename)

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


    with app.app_context():
        db.create_all()
        print("数据库表创建成功！")

        from components.models import Admin
        if not db.session.query(db.exists().where(Admin.account == 'admin')).scalar():
            admin_data = {
                'account': 'admin',
                'username': '超级管理员',
                'phone': '13800138000',
                'email': 'admin@example.com',
                'role': 'SUPER_ADMIN'
            }
            test_admin = Admin.create_with_user(admin_data, '123456')
            print("【初始化】测试管理员创建成功")

    return app


if __name__ == '__main__':
    app = create_app()

    app.run(debug=True, host='0.0.0.0', port=5000)

