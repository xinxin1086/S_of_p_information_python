from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# 合并后的管理员模型（同时支持登录和信息查询）
class Admin(db.Model):
    __tablename__ = 'admin_info'  # 唯一表名
    # 登录所需字段
    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(80), unique=True, nullable=False)  # 登录用户名
    password_hash = db.Column(db.String(255), nullable=False)  # 密码哈希
    # 其他管理员信息字段
    username = db.Column(db.String(120), unique=True, nullable=False)  # 账号（可与username相同）
    phone = db.Column(db.String(20))  # 电话
    email = db.Column(db.String(50))  # 邮箱
    avatar = db.Column(db.String(200))  # 头像
    role = db.Column(db.String(20))  # 角色

    # 密码加密与验证方法（登录用）
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # 动态返回字段信息（供前端表格生成）
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '序号', 'type': 'int'},
            'username': {'label': '登录名', 'type': 'string'},
            'account': {'label': '账号', 'type': 'string'},
            'phone': {'label': '电话', 'type': 'string'},
            'email': {'label': '邮箱', 'type': 'string'},
            'avatar': {'label': '头像', 'type': 'string'},
            'role': {'label': '角色', 'type': 'string'}
        }