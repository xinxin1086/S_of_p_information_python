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
    account = db.Column(db.String(80), nullable=False)  # 登录账号（未注销时唯一）
    password_hash = db.Column(db.String(255), nullable=False)  # 密码哈希
    username = db.Column(db.String(120), nullable=False)  # 显示名称
    phone = db.Column(db.String(20), nullable=False)  # 手机号（未注销时唯一）
    email = db.Column(db.String(50))  # 邮箱
    avatar = db.Column(db.String(200))  # 头像URL
    role = db.Column(db.String(20))  # 角色（USER/ORG_USER等）
    is_deleted = db.Column(db.SmallInteger, nullable=False, default=0, comment='注销标记（0 = 正常，1 = 注销）')  # 软删除标记

    # 添加唯一索引约束（未注销时account和phone唯一）
    __table_args__ = (
        db.Index('idx_account_active', 'account', unique=True,
                 postgresql_where=db.text('is_deleted = 0'),
                 sqlite_where=db.text('is_deleted = 0')),
        db.Index('idx_phone_active', 'phone', unique=True,
                 postgresql_where=db.text('is_deleted = 0'),
                 sqlite_where=db.text('is_deleted = 0')),
    )

    def soft_delete(self):
        """软删除用户，将原信息保存到deleted_user表并匿名化相关数据"""
        if self.is_deleted == 1:
            return None, "用户已经注销"

        # 保存原始账号用于匿名化处理
        original_account = self.account

        # 创建注销记录
        deleted_user = DeletedUser(
            original_user_id=self.id,
            original_account=original_account,
            original_phone=self.phone
        )

        # 软删除用户
        self.is_deleted = 1
        self.account = f"deleted_{self.id}_{self.account}"  # 避免唯一约束冲突
        self.phone = f"deleted_{self.id}_{self.phone}"

        # 匿名化相关数据
        self._anonymize_activity_data(original_account)

        return deleted_user, "注销成功"

    def _anonymize_activity_data(self, original_account):
        """匿名化用户相关的活动数据"""
        from . import db

        try:
            # 1. 匿名化该用户创建的活动（使用username进行查找）
            activities_created = Activity.query.filter_by(
                organizer_user_id=self.id,
                organizer_display=self.username
            ).all()

            for activity in activities_created:
                activity.organizer_display = "用户已注销"
                activity.organizer_user_id = None

            # 2. 匿名化活动评分（使用username进行查找）
            ratings = ActivityRating.query.filter_by(
                rater_user_id=self.id,
                rater_display=self.username
            ).all()

            for rating in ratings:
                rating.update_rater_info()

            # 3. 匿名化活动讨论（使用username进行查找）
            discussions = ActivityDiscuss.query.filter_by(
                author_user_id=self.id,
                author_display=self.username
            ).all()

            for discussion in discussions:
                discussion.update_author_info()

            # 4. 匿名化讨论留言（使用username进行查找）
            discuss_comments = DiscussComment.query.filter_by(
                author_user_id=self.id,
                author_display=self.username
            ).all()

            for comment in discuss_comments:
                comment.update_author_info()

            db.session.commit()

        except Exception as e:
            # 记录错误但不影响注销流程
            print(f"匿名化用户活动数据时出错: {str(e)}")
            db.session.rollback()

    # 字段信息（供前端表格生成，可选）
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '序号', 'type': 'int'},
            'account': {'label': '登录账号', 'type': 'string'},
            'username': {'label': '用户名称', 'type': 'string'},
            'phone': {'label': '手机号', 'type': 'string'},
            'email': {'label': '邮箱', 'type': 'string'},
            'avatar': {'label': '头像', 'type': 'string'},
            'role': {'label': '角色', 'type': 'string'},
            'is_deleted': {'label': '注销状态', 'type': 'boolean', 'options': [(0, '正常'), (1, '已注销')]}
        }


# 已注销用户记录表（对应deleted_user表）
class DeletedUser(db.Model):
    __tablename__ = 'deleted_user'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='注销记录ID')
    original_user_id = db.Column(db.BigInteger, nullable=False, comment='原user_info.id（用户注销后从user_info删除）')
    original_account = db.Column(db.String(50), nullable=False, comment='原用户账号（注销后可复用）')
    original_phone = db.Column(db.String(20), comment='原用户手机号（注销后可复用）')
    delete_time = db.Column(db.DateTime, default=datetime.now, comment='注销时间')

    # 字段信息（供前端表格生成，可选）
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '注销记录ID', 'type': 'bigint', 'readonly': True},
            'original_user_id': {'label': '原用户ID', 'type': 'bigint'},
            'original_account': {'label': '原用户账号', 'type': 'string'},
            'original_phone': {'label': '原手机号', 'type': 'string'},
            'delete_time': {'label': '注销时间', 'type': 'datetime', 'readonly': True}
        }


# 公告模型（对应notice表）修改后：
class Notice(db.Model):
    __tablename__ = 'notice'  # 数据库表名
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='自增主键ID')  # 新增自增ID
    release_time = db.Column(db.DateTime, nullable=False, comment='公告发布时间（不可变更）')  # 改为普通字段
    update_time = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='公告更新时间')  # 新增更新时间
    release_title = db.Column(db.String(150), nullable=False, comment='公告标题')
    release_notice = db.Column(db.Text, nullable=False, comment='公告内容')
    expiration = db.Column(db.DateTime, comment='公告到期时间')
    notice_type = db.Column(db.String(25), nullable=False, default='公告', comment='公告类型')
    attachments = db.Column(db.JSON, comment='附件链接（JSON格式存储）')

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
    description = db.Column(db.Text, comment='活动描述')
    start_time = db.Column(db.DateTime, nullable=False, comment='活动开始时间')
    end_time = db.Column(db.DateTime, nullable=False, comment='活动结束时间')
    location = db.Column(db.String(200), comment='活动地点')
    max_participants = db.Column(db.Integer, nullable=False, comment='最大参与人数')
    current_participants = db.Column(db.Integer, default=0, comment='当前参与人数')
    organizer_user_id = db.Column(db.BigInteger, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='发布者用户ID（关联user_info.id，用户注销后设为 NULL）')
    organizer_display = db.Column(db.String(80), nullable=False, default='用户已注销', comment='发布者显示名（用户注销后改为"用户已注销"）')
    tags = db.Column(db.JSON, comment='活动标签（JSON格式存储）')
    status = db.Column(db.Enum('draft', 'published', 'cancelled', 'completed'), default='draft', comment='活动状态')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关联用户表
    organizer = db.relationship('User', backref='organized_activities', foreign_keys=[organizer_user_id])

    def update_organizer_display(self):
        """更新发布者显示名，支持注销用户匿名化"""
        if self.organizer_user_id and self.organizer and self.organizer.is_deleted == 0:
            # 用户正常存在
            self.organizer_display = self.organizer.username
        else:
            # 用户不存在或已注销，显示匿名信息
            self.organizer_display = "用户已注销"
            self.organizer_user_id = None

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '活动ID', 'type': 'bigint', 'readonly': True},
            'title': {'label': '活动标题', 'type': 'string'},
            'description': {'label': '活动描述', 'type': 'text'},
            'start_time': {'label': '开始时间', 'type': 'datetime'},
            'end_time': {'label': '结束时间', 'type': 'datetime'},
            'location': {'label': '活动地点', 'type': 'string'},
            'max_participants': {'label': '最大参与人数', 'type': 'int'},
            'current_participants': {'label': '当前参与人数', 'type': 'int', 'readonly': True},
            'organizer_user_id': {'label': '发布者用户ID', 'type': 'bigint'},
            'organizer_display': {'label': '发布者显示名', 'type': 'string'},
            'tags': {'label': '活动标签', 'type': 'json'},
            'status': {'label': '状态', 'type': 'enum', 'options': ['draft', 'published', 'cancelled', 'completed']},
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


# 活动评分表（对应activity_rating表）- 增加评语功能
class ActivityRating(db.Model):
    __tablename__ = 'activity_rating'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='评分ID')
    activity_id = db.Column(db.BigInteger, db.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False, comment='关联活动ID')
    rater_user_id = db.Column(db.BigInteger, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='评分用户ID（关联user_info.id，允许NULL）')
    rater_display = db.Column(db.String(80), nullable=False, default='用户已注销', comment='评分用户显示名（注销后匿名化）')
    rater_avatar = db.Column(db.String(200), comment='评分用户头像URL（注销后置为默认头像）')
    score = db.Column(db.SmallInteger, nullable=False, comment='评分值（1-5分）')
    comment_content = db.Column(db.Text, comment='评分内容（可选）')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='评分时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='修改时间')

    # 关联活动表和用户表
    activity = db.relationship('Activity', backref='ratings')
    rater_user = db.relationship('User', backref='activity_ratings', foreign_keys=[rater_user_id])

    # 唯一约束
    __table_args__ = (
        db.UniqueConstraint('rater_user_id', 'activity_id', name='idx_unique_user_activity'),
    )

    def update_rater_info(self):
        """更新评分用户显示信息，支持注销用户匿名化"""
        if self.rater_user_id and self.rater_user and self.rater_user.is_deleted == 0:
            # 用户正常存在
            self.rater_display = self.rater_user.username
            self.rater_avatar = self.rater_user.avatar
        else:
            # 用户不存在或已注销，显示匿名信息
            self.rater_display = "用户已注销"
            self.rater_avatar = "/static/images/default-avatar.png"  # 默认头像
            self.rater_user_id = None

    def set_rater_info(self, user):
        """设置评分用户信息"""
        if user and user.is_deleted == 0:
            self.rater_user_id = user.id
            self.rater_display = user.username
            self.rater_avatar = user.avatar
        else:
            self.rater_user_id = None
            self.rater_display = "用户已注销"
            self.rater_avatar = "/static/images/default-avatar.png"

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '评分ID', 'type': 'bigint', 'readonly': True},
            'activity_id': {'label': '活动ID', 'type': 'bigint'},
            'rater_user_id': {'label': '评分用户ID', 'type': 'bigint'},
            'rater_display': {'label': '评分用户显示名', 'type': 'string'},
            'rater_avatar': {'label': '评分用户头像', 'type': 'string'},
            'score': {'label': '评分值', 'type': 'int', 'min': 1, 'max': 5},
            'comment_content': {'label': '评语内容', 'type': 'text'},
            'create_time': {'label': '评分时间', 'type': 'datetime', 'readonly': True},
            'update_time': {'label': '修改时间', 'type': 'datetime', 'readonly': True}
        }


# 活动讨论表（对应activity_discuss表）- 活动层级可发图片
class ActivityDiscuss(db.Model):
    __tablename__ = 'activity_discuss'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='讨论ID')
    activity_id = db.Column(db.BigInteger, db.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False, comment='关联活动ID（关联activities.id）')
    author_user_id = db.Column(db.BigInteger, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='讨论发布者ID（关联user_info.id，BIGINT类型，允许NULL）')
    author_display = db.Column(db.String(80), nullable=False, default='用户已注销', comment='发布者显示名（注销后匿名化）')
    author_avatar = db.Column(db.String(200), comment='发布者头像URL（注销后置为默认头像）')
    content = db.Column(db.Text, nullable=False, comment='讨论内容（必填）')
    image_urls = db.Column(db.JSON, comment='图片URL列表（支持多张，JSON格式存储，可选）')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='发布时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='修改时间')

    # 关联活动表和用户表
    activity = db.relationship('Activity', backref='discussions')
    author_user = db.relationship('User', backref='activity_discussions', foreign_keys=[author_user_id])

    def update_author_info(self):
        """更新发布者显示信息，支持注销用户匿名化"""
        if self.author_user_id and self.author_user and self.author_user.is_deleted == 0:
            # 用户正常存在
            self.author_display = self.author_user.username
            self.author_avatar = self.author_user.avatar
        else:
            # 用户不存在或已注销，显示匿名信息
            self.author_display = "用户已注销"
            self.author_avatar = "/static/images/default-avatar.png"  # 默认头像
            self.author_user_id = None

    def set_author_info(self, user):
        """设置发布者用户信息"""
        if user and user.is_deleted == 0:
            self.author_user_id = user.id
            self.author_display = user.username
            self.author_avatar = user.avatar
        else:
            self.author_user_id = None
            self.author_display = "用户已注销"
            self.author_avatar = "/static/images/default-avatar.png"

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '讨论ID', 'type': 'bigint', 'readonly': True},
            'activity_id': {'label': '活动ID', 'type': 'bigint'},
            'author_user_id': {'label': '发布者用户ID', 'type': 'bigint'},
            'author_display': {'label': '发布者显示名', 'type': 'string'},
            'author_avatar': {'label': '发布者头像', 'type': 'string'},
            'content': {'label': '讨论内容', 'type': 'text'},
            'image_urls': {'label': '图片URL列表', 'type': 'json'},
            'create_time': {'label': '发布时间', 'type': 'datetime', 'readonly': True},
            'update_time': {'label': '修改时间', 'type': 'datetime', 'readonly': True}
        }


# 活动讨论留言表（对应activity_discuss_comment表）- 不可发图片，支持嵌套回复
class DiscussComment(db.Model):
    __tablename__ = 'activity_discuss_comment'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='留言ID')
    discuss_id = db.Column(db.BigInteger, db.ForeignKey('activity_discuss.id', ondelete='CASCADE'), nullable=False, comment='关联讨论ID（关联activity_discuss.id）')
    author_user_id = db.Column(db.BigInteger, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='留言发布者ID（关联user_info.id，BIGINT类型，允许NULL）')
    author_display = db.Column(db.String(80), nullable=False, default='用户已注销', comment='发布者显示名（注销后匿名化）')
    author_avatar = db.Column(db.String(200), comment='发布者头像URL（注销后置为默认头像）')
    content = db.Column(db.Text, nullable=False, comment='留言内容（必填，不可发图片）')
    parent_comment_id = db.Column(db.BigInteger, db.ForeignKey('activity_discuss_comment.id', ondelete='SET NULL'), nullable=True, comment='父留言ID（支持留言回复，NULL表示直接回复讨论）')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='发布时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='修改时间')

    # 关联讨论表、用户表和自关联
    discuss = db.relationship('ActivityDiscuss', backref='comments')
    author_user = db.relationship('User', backref='discuss_comments', foreign_keys=[author_user_id])
    parent_comment = db.relationship(
        'DiscussComment',
        remote_side=[id],
        foreign_keys=[parent_comment_id],
        primaryjoin='DiscussComment.parent_comment_id==DiscussComment.id',
        backref=db.backref('replies', lazy='dynamic')
    )

    def update_author_info(self):
        """更新发布者显示信息，支持注销用户匿名化"""
        if self.author_user_id and self.author_user and self.author_user.is_deleted == 0:
            # 用户正常存在
            self.author_display = self.author_user.username
            self.author_avatar = self.author_user.avatar
        else:
            # 用户不存在或已注销，显示匿名信息
            self.author_display = "用户已注销"
            self.author_avatar = "/static/images/default-avatar.png"  # 默认头像
            self.author_user_id = None

    def set_author_info(self, user):
        """设置发布者用户信息"""
        if user and user.is_deleted == 0:
            self.author_user_id = user.id
            self.author_display = user.username
            self.author_avatar = user.avatar
        else:
            self.author_user_id = None
            self.author_display = "用户已注销"
            self.author_avatar = "/static/images/default-avatar.png"

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '留言ID', 'type': 'bigint', 'readonly': True},
            'discuss_id': {'label': '讨论ID', 'type': 'bigint'},
            'author_user_id': {'label': '发布者用户ID', 'type': 'bigint'},
            'author_display': {'label': '发布者显示名', 'type': 'string'},
            'author_avatar': {'label': '发布者头像', 'type': 'string'},
            'content': {'label': '留言内容', 'type': 'text'},
            'parent_comment_id': {'label': '父留言ID', 'type': 'bigint'},
            'create_time': {'label': '发布时间', 'type': 'datetime', 'readonly': True},
            'update_time': {'label': '修改时间', 'type': 'datetime', 'readonly': True}
        }
