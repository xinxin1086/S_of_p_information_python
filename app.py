from flask import Flask
from models import db, Admin
from routes import api
from config import Config
from flask_cors import CORS

# 初始化app后配置CORS
app = Flask(__name__)

app.config.from_object(Config)
db.init_app(app)

app.register_blueprint(api, url_prefix='/api')
# 允许跨域，支持带Authorization头的请求
CORS(app, resources={
    r"/api/*": {
        "origins": "*",  # 生产环境建议指定具体前端域名 "http://localhost:5173"
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# 可选：单独处理OPTIONS请求（如果CORS配置未生效）
@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return '', 200, {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }


with app.app_context():
    db.create_all()
    # 添加测试管理员
    if not db.session.query(db.exists().where(Admin.username == 'admin')).scalar():
        test_admin = Admin(
            username='admin',
            account='admin',
            phone='13800138000',
            email='admin@example.com',
            role='ADMIN'
        )
        test_admin.set_password('123456')
        db.session.add(test_admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, port=5000)