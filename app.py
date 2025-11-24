from flask import Flask
import os
from flask_cors import CORS
from config import Config
from components import db  # 引用公共数据库
from admin import admin_bp  # 导入管理员蓝图
from user import user_bp  # 导入用户蓝图
from common import common_bp  # 导入公共蓝图
from flask import send_from_directory  # 导入图片静态路由
from visit import visit_bp  # 导入visit蓝图


# 初始化Flask应用
app = Flask(__name__)
app.config.from_object(Config)

# 配置CORS（允许跨域）
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# 初始化数据库
db.init_app(app)

# 注册蓝图（管理员接口）
app.register_blueprint(admin_bp)
# 注册蓝图（用户接口）
app.register_blueprint(user_bp)
# 注册蓝图（公共接口）
app.register_blueprint(common_bp)
# 注册visit蓝图（访问接口）
app.register_blueprint(visit_bp)


# 图片静态路由
@app.route('/static/images/<filename>')
def serve_image(filename):
    image_dir = app.config['IMAGE_STORAGE_DIR']
    return send_from_directory(os.path.abspath(image_dir), filename)

# 初始化数据库表和测试数据
with app.app_context():
    db.create_all()
    from components.models import Admin  # 局部导入避免循环引用
    # 添加测试管理员（若不存在）
    if not db.session.query(db.exists().where(Admin.account == 'admin')).scalar():
        test_admin = Admin(
            account='admin',
            username='系统管理员',
            phone='13800138000',
            email='admin@example.com',
            role='ADMIN'
        )
        test_admin.set_password('admin123')  # 密码：admin123
        db.session.add(test_admin)
        db.session.commit()
        print("【初始化】测试管理员创建成功")

if __name__ == '__main__':
    app.run(debug=True, port=5000)