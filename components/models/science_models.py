# 科普相关模型

from datetime import datetime
from .base import db
from .user_models import User


# 科普文章模型（对应science_articles表）
class ScienceArticle(db.Model):
    __tablename__ = 'science_articles'
    __table_args__ = {'mysql_comment': '科普文章表：存储科普文章的内容和状态信息', 'comment': '科普文章表：存储科普文章的内容和状态信息'}
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='文章唯一标识')
    title = db.Column(db.String(200), nullable=False, comment='文章标题')
    content = db.Column(db.Text, nullable=False, comment='文章内容')
    cover_image = db.Column(db.String(255), comment='封面图片URL')
    status = db.Column(db.Enum('draft', 'pending', 'published', 'rejected'), default='draft', comment='文章状态')
    like_count = db.Column(db.Integer, default=0, comment='点赞次数')
    view_count = db.Column(db.Integer, default=0, comment='浏览次数')
    published_at = db.Column(db.DateTime, comment='发布时间')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 发布者系统 - 统一使用用户表
    author_user_id = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='发布者用户ID（关联user_info.id，包含所有用户类型，用户注销后设为 NULL）')
    author_display = db.Column(db.String(80), nullable=False, default='用户已注销', comment='发布者显示名（用户注销后改为"用户已注销"）')

    # 关联关系
    author_user = db.relationship('User', backref='science_articles_authored', foreign_keys=[author_user_id])

    def update_author_display(self):
        """更新发布者显示名，支持注销用户匿名化"""
        if self.author_user_id and self.author_user and self.author_user.is_deleted == 0:
            # 根据用户角色显示不同的前缀
            if self.author_user.role == 'ADMIN':
                role_prefix = "管理员"
            elif self.author_user.role == 'ORG_USER':
                role_prefix = "组织用户"
            else:
                role_prefix = "用户"
            self.author_display = f"{self.author_user.username}（{role_prefix}）"
        else:
            # 用户不存在或已注销，显示匿名信息
            self.author_display = "用户已注销"
            self.author_user_id = None

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '文章ID', 'type': 'bigint', 'readonly': True},
            'title': {'label': '文章标题', 'type': 'string'},
            'content': {'label': '文章内容', 'type': 'text'},
            'author_display': {'label': '发布者', 'type': 'string', 'readonly': True},
            'cover_image': {'label': '封面图片', 'type': 'string'},
            'status': {'label': '状态', 'type': 'enum', 'options': ['draft', 'pending', 'published', 'rejected']},
            'like_count': {'label': '点赞次数', 'type': 'int', 'readonly': True},
            'view_count': {'label': '浏览次数', 'type': 'int', 'readonly': True},
            'published_at': {'label': '发布时间', 'type': 'datetime'},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True},
            'updated_at': {'label': '更新时间', 'type': 'datetime', 'readonly': True}
        }


# 科普文章点赞模型（对应science_article_likes表）
class ScienceArticleLike(db.Model):
    __tablename__ = 'science_article_likes'
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='点赞记录ID')
    user_id = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='CASCADE'), nullable=False, comment='点赞用户ID（关联user_info.id，包含所有用户类型）')
    article_id = db.Column(db.Integer, db.ForeignKey('science_articles.id', ondelete='CASCADE'), nullable=False, comment='关联科普文章ID（science_articles.id）')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='点赞时间')

    # 关联表
    user = db.relationship('User', backref='science_article_likes', foreign_keys=[user_id])
    article = db.relationship('ScienceArticle', backref='likes')

    # 唯一约束：每个用户对每篇文章只能点赞一次
    __table_args__ = (
        db.UniqueConstraint('user_id', 'article_id', name='idx_unique_article_like'),
        {'mysql_comment': '科普文章点赞表：记录用户对科普文章的点赞信息', 'comment': '科普文章点赞表：记录用户对科普文章的点赞信息'}
    )

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '点赞记录ID', 'type': 'bigint', 'readonly': True},
            'user_id': {'label': '用户ID', 'type': 'bigint'},
            'article_id': {'label': '文章ID', 'type': 'bigint'},
            'created_at': {'label': '点赞时间', 'type': 'datetime', 'readonly': True}
        }


# 科普文章浏览模型（对应science_article_visits表）
class ScienceArticleVisit(db.Model):
    __tablename__ = 'science_article_visits'
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='浏览记录ID')
    user_id = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='CASCADE'), nullable=False, comment='浏览用户ID（关联user_info.id，包含所有用户类型）')
    article_id = db.Column(db.Integer, db.ForeignKey('science_articles.id', ondelete='CASCADE'), nullable=False, comment='关联科普文章ID（science_articles.id）')
    first_visit_at = db.Column(db.DateTime, default=datetime.now, comment='首次浏览时间')
    last_visit_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='最后浏览时间')

    # 关联表
    user = db.relationship('User', backref='science_article_visits', foreign_keys=[user_id])
    article = db.relationship('ScienceArticle', backref='visits')

    # 唯一约束：每个用户对每篇文章只有一条浏览记录
    __table_args__ = (
        db.UniqueConstraint('user_id', 'article_id', name='idx_unique_article_visit'),
        {'mysql_comment': '科普文章浏览记录表：记录用户对科普文章的浏览历史', 'comment': '科普文章浏览记录表：记录用户对科普文章的浏览历史'}
    )

    # 动态字段信息
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '浏览记录ID', 'type': 'bigint', 'readonly': True},
            'user_id': {'label': '用户ID', 'type': 'bigint'},
            'article_id': {'label': '文章ID', 'type': 'bigint'},
            'first_visit_at': {'label': '首次浏览时间', 'type': 'datetime', 'readonly': True},
            'last_visit_at': {'label': '最后浏览时间', 'type': 'datetime', 'readonly': True}
        }