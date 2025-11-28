# ./components/models.py

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


# 公告模型（对应notice表）修改后：
class Notice(db.Model):
    __tablename__ = 'notice'  # 数据库表名
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='自增主键ID')  # 新增自增ID
    release_time = db.Column(db.DateTime, nullable=False, comment='公告发布时间（不可变更）')  # 改为普通字段
    update_time = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='公告更新时间')  # 新增更新时间
    release_title = db.Column(db.String(150), nullable=False, comment='公告发布标题')
    release_notice = db.Column(db.String(255), nullable=False, comment='发布公告内容')
    expiration = db.Column(db.DateTime, comment='公到期时间')
    notice_type = db.Column(db.String(25), comment='公告类型')
    attachments = db.Column(db.Text, comment='附件链接（JSON格式存储多个附件ID）')

    # 动态字段信息（供前端表格生成）
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '公告ID', 'type': 'bigint', 'readonly': True},  # 自增ID只读
            'release_time': {'label': '发布时间', 'type': 'datetime', 'readonly': True},  # 发布时间只读
            'update_time': {'label': '更新时间', 'type': 'datetime', 'readonly': True},  # 更新时间只读
            'release_title': {'label': '公告标题', 'type': 'string'},
            'release_notice': {'label': '公告内容', 'type': 'string'},
            'expiration': {'label': '到期时间', 'type': 'datetime'},
            'notice_type': {'label': '公告类型', 'type': 'string'},
            'attachments': {'label': '附件链接', 'type': 'json'}
        }


# 科普文章模型（对应science_articles表）
class ScienceArticle(db.Model):
    __tablename__ = 'science_articles'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='文章唯一标识')
    title = db.Column(db.String(200), nullable=False, comment='文章标题')
    content = db.Column(db.Text, nullable=False, comment='文章内容')
    author_account = db.Column(db.String(80), db.ForeignKey('user_info.account'), nullable=False, comment='作者账号')
    cover_image = db.Column(db.String(255), comment='封面图片URL')
    status = db.Column(db.Enum('draft', 'pending', 'published', 'rejected'), default='draft', comment='文章状态')
    like_count = db.Column(db.Integer, default=0, comment='点赞次数')
    view_count = db.Column(db.Integer, default=0, comment='浏览次数')
    published_at = db.Column(db.DateTime, comment='发布时间')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关联用户表
    author = db.relationship('User', backref='science_articles', foreign_keys=[author_account])

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '文章ID', 'type': 'bigint', 'readonly': True},
            'title': {'label': '文章标题', 'type': 'string'},
            'content': {'label': '文章内容', 'type': 'text'},
            'author_account': {'label': '作者账号', 'type': 'string'},
            'cover_image': {'label': '封面图片', 'type': 'string'},
            'status': {'label': '状态', 'type': 'enum', 'options': ['draft', 'pending', 'published', 'rejected']},
            'like_count': {'label': '点赞次数', 'type': 'int', 'readonly': True},
            'view_count': {'label': '浏览次数', 'type': 'int', 'readonly': True},
            'published_at': {'label': '发布时间', 'type': 'datetime'},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True},
            'updated_at': {'label': '更新时间', 'type': 'datetime', 'readonly': True}
        }


# 活动模型（对应activities表）
class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='活动唯一标识')
    title = db.Column(db.String(200), nullable=False, comment='活动标题')
    description = db.Column(db.Text, nullable=False, comment='活动描述')
    organizer_account = db.Column(db.String(80), db.ForeignKey('user_info.account'), nullable=False, comment='组织者账号')
    location = db.Column(db.String(200), comment='活动地点')
    start_time = db.Column(db.DateTime, nullable=False, comment='开始时间')
    end_time = db.Column(db.DateTime, nullable=False, comment='结束时间')
    max_participants = db.Column(db.Integer, comment='最大参与人数')
    current_participants = db.Column(db.Integer, default=0, comment='当前参与人数')
    status = db.Column(db.Enum('draft', 'published', 'ongoing', 'completed', 'cancelled'), default='draft', comment='活动状态')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关联用户表
    organizer = db.relationship('User', backref='organized_activities', foreign_keys=[organizer_account])

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '活动ID', 'type': 'bigint', 'readonly': True},
            'title': {'label': '活动标题', 'type': 'string'},
            'description': {'label': '活动描述', 'type': 'text'},
            'organizer_account': {'label': '组织者账号', 'type': 'string'},
            'location': {'label': '活动地点', 'type': 'string'},
            'start_time': {'label': '开始时间', 'type': 'datetime'},
            'end_time': {'label': '结束时间', 'type': 'datetime'},
            'max_participants': {'label': '最大参与人数', 'type': 'int'},
            'current_participants': {'label': '当前参与人数', 'type': 'int', 'readonly': True},
            'status': {'label': '状态', 'type': 'enum', 'options': ['draft', 'published', 'ongoing', 'completed', 'cancelled']},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True},
            'updated_at': {'label': '更新时间', 'type': 'datetime', 'readonly': True}
        }


# 活动预约模型（对应activity_bookings表）
class ActivityBooking(db.Model):
    __tablename__ = 'activity_bookings'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='预约唯一标识')
    activity_id = db.Column(db.BigInteger, db.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False, comment='活动ID')
    user_account = db.Column(db.String(80), db.ForeignKey('user_info.account'), nullable=False, comment='用户账号')
    booking_time = db.Column(db.DateTime, default=datetime.now, comment='预约时间')
    status = db.Column(db.Enum('booked', 'cancelled', 'attended'), default='booked', comment='预约状态')
    notes = db.Column(db.Text, comment='备注')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关联活动表和用户表
    activity = db.relationship('Activity', backref='bookings')
    user = db.relationship('User', backref='activity_bookings')

    # 唯一约束
    __table_args__ = (
        db.UniqueConstraint('activity_id', 'user_account', name='unique_booking'),
    )

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '预约ID', 'type': 'bigint', 'readonly': True},
            'activity_id': {'label': '活动ID', 'type': 'bigint'},
            'user_account': {'label': '用户账号', 'type': 'string'},
            'booking_time': {'label': '预约时间', 'type': 'datetime', 'readonly': True},
            'status': {'label': '预约状态', 'type': 'enum', 'options': ['booked', 'cancelled', 'attended']},
            'notes': {'label': '备注', 'type': 'text'},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True},
            'updated_at': {'label': '更新时间', 'type': 'datetime', 'readonly': True}
        }


# 活动评论模型（对应activity_comments表）
class ActivityComment(db.Model):
    __tablename__ = 'activity_comments'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='评论唯一标识')
    activity_id = db.Column(db.BigInteger, db.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False, comment='活动ID')
    user_account = db.Column(db.String(80), db.ForeignKey('user_info.account'), nullable=False, comment='用户账号')
    content = db.Column(db.Text, nullable=False, comment='评论内容')
    rating = db.Column(db.SmallInteger, comment='评分1-5')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关联活动表和用户表
    activity = db.relationship('Activity', backref='comments')
    user = db.relationship('User', backref='activity_comments')

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '评论ID', 'type': 'bigint', 'readonly': True},
            'activity_id': {'label': '活动ID', 'type': 'bigint'},
            'user_account': {'label': '用户账号', 'type': 'string'},
            'content': {'label': '评论内容', 'type': 'text'},
            'rating': {'label': '评分', 'type': 'int', 'min': 1, 'max': 5},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True},
            'updated_at': {'label': '更新时间', 'type': 'datetime', 'readonly': True}
        }


# 论坛帖子模型（对应forum_posts表）
class ForumPost(db.Model):
    __tablename__ = 'forum_posts'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='帖子唯一标识')
    title = db.Column(db.String(200), nullable=False, comment='帖子标题')
    content = db.Column(db.Text, nullable=False, comment='帖子内容')
    author_account = db.Column(db.String(80), db.ForeignKey('user_info.account'), nullable=False, comment='作者账号')
    category = db.Column(db.String(50), default='default', comment='分类')
    view_count = db.Column(db.Integer, default=0, comment='浏览次数')
    like_count = db.Column(db.Integer, default=0, comment='点赞次数')
    comment_count = db.Column(db.Integer, default=0, comment='评论次数')
    status = db.Column(db.Enum('published', 'draft', 'deleted'), default='published', comment='帖子状态')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关联用户表
    author = db.relationship('User', backref='forum_posts', foreign_keys=[author_account])

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '帖子ID', 'type': 'bigint', 'readonly': True},
            'title': {'label': '帖子标题', 'type': 'string'},
            'content': {'label': '帖子内容', 'type': 'text'},
            'author_account': {'label': '作者账号', 'type': 'string'},
            'category': {'label': '分类', 'type': 'string'},
            'view_count': {'label': '浏览次数', 'type': 'int', 'readonly': True},
            'like_count': {'label': '点赞次数', 'type': 'int', 'readonly': True},
            'comment_count': {'label': '评论次数', 'type': 'int', 'readonly': True},
            'status': {'label': '状态', 'type': 'enum', 'options': ['published', 'draft', 'deleted']},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True},
            'updated_at': {'label': '更新时间', 'type': 'datetime', 'readonly': True}
        }


# 论坛评论模型（对应forum_comments表）
class ForumComment(db.Model):
    __tablename__ = 'forum_comments'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='评论唯一标识')
    post_id = db.Column(db.BigInteger, db.ForeignKey('forum_posts.id', ondelete='CASCADE'), nullable=False, comment='帖子ID')
    author_account = db.Column(db.String(80), db.ForeignKey('user_info.account'), nullable=False, comment='评论者账号')
    content = db.Column(db.Text, nullable=False, comment='评论内容')
    parent_id = db.Column(db.BigInteger, db.ForeignKey('forum_comments.id'), comment='父评论ID')
    status = db.Column(db.Enum('published', 'deleted'), default='published', comment='评论状态')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    # 关联帖子表、用户表和自关联
    post = db.relationship('ForumPost', backref='comments')
    author = db.relationship('User', backref='forum_comments', foreign_keys=[author_account])
    parent_comment = db.relationship('ForumComment', remote_side=[id], backref='replies')

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '评论ID', 'type': 'bigint', 'readonly': True},
            'post_id': {'label': '帖子ID', 'type': 'bigint'},
            'author_account': {'label': '评论者账号', 'type': 'string'},
            'content': {'label': '评论内容', 'type': 'text'},
            'parent_id': {'label': '父评论ID', 'type': 'bigint'},
            'status': {'label': '状态', 'type': 'enum', 'options': ['published', 'deleted']},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True}
        }


# 用户点赞模型（对应user_likes表）
class UserLike(db.Model):
    __tablename__ = 'user_likes'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='点赞唯一标识')
    user_account = db.Column(db.String(80), db.ForeignKey('user_info.account'), nullable=False, comment='用户账号')
    target_type = db.Column(db.Enum('post', 'article', 'comment'), nullable=False, comment='目标类型')
    target_id = db.Column(db.BigInteger, nullable=False, comment='目标ID')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    # 关联用户表
    user = db.relationship('User', backref='user_likes')

    # 唯一约束
    __table_args__ = (
        db.UniqueConstraint('user_account', 'target_type', 'target_id', name='unique_like'),
    )

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '点赞ID', 'type': 'bigint', 'readonly': True},
            'user_account': {'label': '用户账号', 'type': 'string'},
            'target_type': {'label': '目标类型', 'type': 'enum', 'options': ['post', 'article', 'comment']},
            'target_id': {'label': '目标ID', 'type': 'bigint'},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True}
        }


# 附件模型（对应attachments表）
class Attachment(db.Model):
    __tablename__ = 'attachments'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='附件唯一标识')
    uploader_account = db.Column(db.String(80), db.ForeignKey('user_info.account'), nullable=False, comment='上传者账号')
    file_name = db.Column(db.String(255), nullable=False, comment='文件名')
    file_path = db.Column(db.String(500), nullable=False, comment='文件路径')
    file_size = db.Column(db.BigInteger, nullable=False, comment='文件大小')
    file_type = db.Column(db.String(50), nullable=False, comment='文件类型')
    usage_type = db.Column(db.Enum('avatar', 'cover', 'attachment'), nullable=False, comment='用途类型')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    # 关联用户表
    uploader = db.relationship('User', backref='attachments')

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '附件ID', 'type': 'bigint', 'readonly': True},
            'uploader_account': {'label': '上传者账号', 'type': 'string'},
            'file_name': {'label': '文件名', 'type': 'string'},
            'file_path': {'label': '文件路径', 'type': 'string'},
            'file_size': {'label': '文件大小', 'type': 'bigint'},
            'file_type': {'label': '文件类型', 'type': 'string'},
            'usage_type': {'label': '用途类型', 'type': 'enum', 'options': ['avatar', 'cover', 'attachment']},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True}
        }
