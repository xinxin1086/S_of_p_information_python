from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# 初始化数据库（所有模块共享）
db = SQLAlchemy()


# 基类模型，包含密码加密与验证的方法
class BaseUser(db.Model):
    __abstract__ = True

    def set_password(self, password):
        if not isinstance(password, str) or not password:
            raise ValueError('密码必须是非空字符串')
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not isinstance(password, str) or not password:
            raise ValueError('密码必须是非空字符串')
        return check_password_hash(self.password_hash, password)


# 管理员模型（仅管理员模块使用，但定义在公共组件中供共享）
class Admin(BaseUser):
    __tablename__ = 'admin_info'
    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(80), unique=True, nullable=False)  # 登录账号
    password_hash = db.Column(db.String(255), nullable=False)  # 密码哈希
    username = db.Column(db.String(120), nullable=False)  # 显示名称
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(50))
    avatar = db.Column(db.String(200))
    role = db.Column(db.String(20))  # 角色（ADMIN/USER）

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


# 新增User模型（对应user_info表）
class User(BaseUser):
    __tablename__ = 'user_info'
    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(80), unique=True, nullable=False)  # 登录账号
    password_hash = db.Column(db.String(255), nullable=False)  # 密码哈希
    username = db.Column(db.String(120), unique=True, nullable=False)  # 显示名称
    phone = db.Column(db.String(20), nullable=False)  # 电话（非空）
    email = db.Column(db.String(50))  # 邮箱（可空）
    avatar = db.Column(db.String(200))  # 头像（存储图片URL）
    role = db.Column(db.String(20))  # 角色

    # 字段信息（供前端表格生成，可选）
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '序号', 'type': 'int'},
            'account': {'label': '登录账号', 'type': 'string'},
            'username': {'label': '用户名称', 'type': 'string'},
            'phone': {'label': '电话', 'type': 'string'},
            'email': {'label': '邮箱', 'type': 'string'},
            'avatar': {'label': '头像', 'type': 'string'},
            'role': {'label': '角色', 'type': 'string'}
        }


# 新增公告模型（对应notice表）
class Notice(db.Model):
    __tablename__ = 'notice'  # 数据库表名
    release_time = db.Column(db.DateTime, nullable=False, primary_key=True, comment='公告发布时间')  # 主键
    release_title = db.Column(db.String(150), nullable=False, comment='公告发布标题')
    release_notice = db.Column(db.String(255), nullable=False, comment='发布公告内容')
    expiration = db.Column(db.DateTime, comment='公到期时间')
    notice_type = db.Column(db.String(25), comment='公告类型')

    # 动态字段信息（供前端表格生成）
    @classmethod
    def get_fields_info(cls):
        return {
            'release_time': {'label': '发布时间', 'type': 'datetime'},
            'release_title': {'label': '公告标题', 'type': 'string'},
            'release_notice': {'label': '公告内容', 'type': 'string'},
            'expiration': {'label': '到期时间', 'type': 'datetime'},
            'notice_type': {'label': '公告类型', 'type': 'string'}
        }
