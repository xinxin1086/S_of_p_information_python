from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# 初始化数据库（所有模块共享）
db = SQLAlchemy()

# 管理员模型（仅管理员模块使用，但定义在公共组件中供共享）
class Admin(db.Model):
    __tablename__ = 'admin_info'
    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(80), unique=True, nullable=False)  # 登录账号
    password_hash = db.Column(db.String(255), nullable=False)  # 密码哈希
    username = db.Column(db.String(120), nullable=False)  # 显示名称
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(50))
    avatar = db.Column(db.String(200))
    role = db.Column(db.String(20))  # 角色（ADMIN/USER）

    # 密码加密与验证
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # 动态字段信息（供前端表格生成）
    @classmethod
    def get_fields_info(cls):
        return {
            'account': {'label': '登录账号', 'type': 'string'},
            'username': {'label': '用户名称', 'type': 'string'},
            'phone': {'label': '电话', 'type': 'string'},
            'email': {'label': '邮箱', 'type': 'string'},
            'avatar': {'label': '头像', 'type': 'string'},
            'role': {'label': '角色', 'type': 'string'}
        }