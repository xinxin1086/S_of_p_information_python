# 活动管理相关模型

from datetime import datetime
from .base import db
from .user_models import User


# 活动模型（对应activities表）
class Activity(db.Model):
    __tablename__ = 'activities'
    __table_args__ = {'mysql_comment': '活动信息表：存储各类活动的基本信息和状态', 'comment': '活动信息表：存储各类活动的基本信息和状态'}
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='活动唯一标识')
    title = db.Column(db.String(200), nullable=False, comment='活动标题')
    description = db.Column(db.Text, comment='活动描述')
    start_time = db.Column(db.DateTime, nullable=False, comment='活动开始时间')
    end_time = db.Column(db.DateTime, nullable=False, comment='活动结束时间')
    location = db.Column(db.String(200), comment='活动地点')
    max_participants = db.Column(db.Integer, nullable=False, comment='最大参与人数')
    current_participants = db.Column(db.Integer, default=0, comment='当前参与人数')
    organizer_user_id = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='发布者用户ID（关联user_info.id，用户注销后设为 NULL）')
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
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='预约唯一标识')
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False, comment='活动ID')
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
        {'mysql_comment': '活动预约表：记录用户参与活动的预约信息', 'comment': '活动预约表：记录用户参与活动的预约信息'}
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


# 活动评分表（对应activity_rating表）- 增加评语功能
class ActivityRating(db.Model):
    __tablename__ = 'activity_rating'
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='评分ID')
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False, comment='关联活动ID')
    rater_user_id = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='评分用户ID（关联user_info.id，允许NULL）')
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
        {'mysql_comment': '活动评分表：记录用户对活动的评分和评价', 'comment': '活动评分表：记录用户对活动的评分和评价'}
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
    __table_args__ = {'mysql_comment': '活动讨论表：存储用户对活动的讨论内容', 'comment': '活动讨论表：存储用户对活动的讨论内容'}
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='讨论ID')
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False, comment='关联活动ID（关联activities.id）')
    author_user_id = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='讨论发布者ID（关联user_info.id，BIGINT类型，允许NULL）')
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
class ActivityDiscussComment(db.Model):
    __tablename__ = 'activity_discuss_comment'
    __table_args__ = {'mysql_comment': '活动讨论留言表：存储对讨论的回复和评论', 'comment': '活动讨论留言表：存储对讨论的回复和评论'}
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='留言ID')
    discuss_id = db.Column(db.Integer, db.ForeignKey('activity_discuss.id', ondelete='CASCADE'), nullable=False, comment='关联讨论ID（关联activity_discuss.id）')
    author_user_id = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='留言发布者ID（关联user_info.id，BIGINT类型，允许NULL）')
    author_display = db.Column(db.String(80), nullable=False, default='用户已注销', comment='发布者显示名（注销后匿名化）')
    author_avatar = db.Column(db.String(200), comment='发布者头像URL（注销后置为默认头像）')
    content = db.Column(db.Text, nullable=False, comment='留言内容（必填，不可发图片）')
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('activity_discuss_comment.id', ondelete='SET NULL'), nullable=True, comment='父留言ID（支持留言回复，NULL表示直接回复讨论）')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='发布时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='修改时间')

    # 关联讨论表、用户表和自关联
    discuss = db.relationship('ActivityDiscuss', backref='comments')
    author_user = db.relationship('User', backref='discuss_comments', foreign_keys=[author_user_id])
    parent_comment = db.relationship(
        'ActivityDiscussComment',
        remote_side=[id],
        foreign_keys=[parent_comment_id],
        primaryjoin='ActivityDiscussComment.parent_comment_id==ActivityDiscussComment.id',
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