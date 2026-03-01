
from datetime import datetime
from .base import db
from .user_models import User


class ForumPost(db.Model):
    __tablename__ = 'forum_posts'
    __table_args__ = {'mysql_comment': '论坛帖子表：存储论坛主帖的信息和内容', 'comment': '论坛帖子表：存储论坛主帖的信息和内容'}
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='帖子唯一标识')
    title = db.Column(db.String(200), nullable=False, comment='帖子标题')
    content = db.Column(db.Text, nullable=False, comment='帖子内容')
    category = db.Column(db.String(50), default='default', comment='分类')
    view_count = db.Column(db.Integer, default=0, comment='浏览次数')
    like_count = db.Column(db.Integer, default=0, comment='点赞次数')
    comment_count = db.Column(db.Integer, default=0, comment='评论次数')
    status = db.Column(db.Enum('published', 'draft', 'deleted'), default='published', comment='帖子状态')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    author_user_id = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='发布者用户ID（关联user_info.id，包含所有用户类型，用户注销后设为 NULL）')
    author_display = db.Column(db.String(80), nullable=False, default='用户已注销', comment='发布者显示名（用户注销后改为"用户已注销"）')

    author_user = db.relationship('User', backref='forum_posts_authored', foreign_keys=[author_user_id])
    floors = db.relationship('ForumFloor', backref='post_floor', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('ForumLike', backref='liked_post', lazy='dynamic', cascade='all, delete-orphan', primaryjoin="and_(ForumPost.id==ForumLike.post_id, ForumLike.target_type=='post')")
    visits = db.relationship('ForumVisit', backref='visited_post', lazy='dynamic', cascade='all, delete-orphan')

    def update_author_display(self):
        
        if self.author_user_id and self.author_user and self.author_user.is_deleted == 0:
            if self.author_user.role == 'SUPER_ADMIN' or self.author_user.role == 'ADMIN':
                role_prefix = "管理员"
            elif self.author_user.role == 'ORG_USER':
                role_prefix = "组织用户"
            else:
                role_prefix = "用户"
            self.author_display = f"{self.author_user.username}（{role_prefix}）"
        else:
            self.author_display = "用户已注销"
            self.author_user_id = None

    def increment_view_count(self, user_id=None):
        
        self.view_count += 1

        if user_id:
            from . import db
            existing_visit = ForumVisit.query.filter_by(
                post_id=self.id,
                user_id=user_id
            ).first()

            if not existing_visit:
                visit = ForumVisit(
                    post_id=self.id,
                    user_id=user_id
                )
                db.session.add(visit)
            else:
                existing_visit.last_visit_at = datetime.now()

        db.session.commit()
        return self.view_count

    def calculate_like_count(self):
        
        return ForumLike.query.filter_by(
            post_id=self.id,
            target_type='post'
        ).count()

    def calculate_comment_count(self):
        
        return ForumFloor.query.filter_by(
            post_id=self.id,
            status='published'
        ).count()

    def update_counts(self):
        
        self.like_count = self.calculate_like_count()
        self.comment_count = self.calculate_comment_count()
        db.session.commit()

    @property
    def actual_like_count(self):
        
        return self.calculate_like_count()

    @property
    def actual_comment_count(self):
        
        return self.calculate_comment_count()

    @property
    def actual_view_count(self):
        
        return self.view_count

    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '帖子ID', 'type': 'bigint', 'readonly': True},
            'title': {'label': '帖子标题', 'type': 'string'},
            'content': {'label': '帖子内容', 'type': 'text'},
            'author_display': {'label': '发布者', 'type': 'string', 'readonly': True},
            'category': {'label': '分类', 'type': 'string'},
            'view_count': {'label': '浏览次数', 'type': 'int', 'readonly': True},
            'like_count': {'label': '点赞次数', 'type': 'int', 'readonly': True},
            'comment_count': {'label': '评论次数', 'type': 'int', 'readonly': True},
            'status': {'label': '状态', 'type': 'enum', 'options': ['published', 'draft', 'deleted']},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True},
            'updated_at': {'label': '更新时间', 'type': 'datetime', 'readonly': True}
        }


class ForumFloor(db.Model):
    __tablename__ = 'forum_floors'
    __table_args__ = {'mysql_comment': '论坛楼层表：存储对帖子的直接回复（楼层内容）', 'comment': '论坛楼层表：存储对帖子的直接回复（楼层内容）'}
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='楼层唯一标识')
    post_id = db.Column(db.Integer, db.ForeignKey('forum_posts.id', ondelete='CASCADE'), nullable=False, comment='帖子ID')
    content = db.Column(db.Text, nullable=False, comment='楼层内容')
    floor_number = db.Column(db.Integer, nullable=False, comment='楼层号（1楼、2楼...）')
    like_count = db.Column(db.Integer, default=0, comment='点赞次数')
    reply_count = db.Column(db.Integer, default=0, comment='回复次数')
    status = db.Column(db.Enum('published', 'deleted'), default='published', comment='楼层状态')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    author_user_id = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='楼主用户ID（关联user_info.id，包含所有用户类型，用户注销后设为 NULL）')
    author_display = db.Column(db.String(80), nullable=False, default='用户已注销', comment='楼主显示名（用户注销后改为"用户已注销"）')

    author_user = db.relationship('User', backref='forum_floors_authored', foreign_keys=[author_user_id])
    replies = db.relationship('ForumReply', backref='parent_floor', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('ForumLike', backref='liked_floor', lazy='dynamic', cascade='all, delete-orphan', primaryjoin="and_(ForumFloor.id==ForumLike.floor_id, ForumLike.target_type=='floor')")

    def update_author_display(self):
        
        if self.author_user_id and self.author_user and self.author_user.is_deleted == 0:
            if self.author_user.role == 'SUPER_ADMIN' or self.author_user.role == 'ADMIN':
                role_prefix = "管理员"
            elif self.author_user.role == 'ORG_USER':
                role_prefix = "组织用户"
            else:
                role_prefix = "用户"
            self.author_display = f"{self.author_user.username}（{role_prefix}）"
        else:
            self.author_display = "用户已注销"
            self.author_user_id = None

    @classmethod
    def create_floor(cls, post_id, user_id, content):
        
        from . import db

        post = ForumPost.query.get(post_id)
        if not post:
            return None

        max_floor = db.session.query(db.func.max(cls.floor_number)).filter_by(
            post_id=post_id
        ).scalar() or 0
        floor_number = max_floor + 1

        floor = cls(
            post_id=post_id,
            author_user_id=user_id,
            content=content,
            floor_number=floor_number
        )
        floor.update_author_display()

        db.session.add(floor)

        post.comment_count += 1

        db.session.commit()
        return floor

    def delete_floor(self):
        
        from . import db

        if self.post and self.post.comment_count > 0:
            self.post.comment_count -= 1

        db.session.delete(self)
        db.session.commit()

    def calculate_like_count(self):
        
        return ForumLike.query.filter_by(
            floor_id=self.id,
            target_type='floor'
        ).count()

    def calculate_reply_count(self):
        
        return ForumReply.query.filter_by(
            floor_id=self.id,
            status='published'
        ).count()

    def update_counts(self):
        
        self.like_count = self.calculate_like_count()
        self.reply_count = self.calculate_reply_count()
        db.session.commit()

    def get_floor_display(self):
        
        return f"#{self.floor_number}楼"

    @classmethod
    def get_floors_by_post(cls, post_id, page=1, per_page=20):
        
        from . import db

        floors_query = cls.query.filter_by(
            post_id=post_id,
            status='published'
        ).order_by(cls.floor_number.asc())

        floors_pagination = floors_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

        floors_with_replies = []
        for floor in floors_pagination.items:
            recent_replies = ForumReply.query.filter_by(
                floor_id=floor.id,
                status='published'
            ).order_by(ForumReply.created_at.desc()).limit(3).all()

            total_replies = ForumReply.query.filter_by(
                floor_id=floor.id,
                status='published'
            ).count()

            floors_with_replies.append({
                'floor': floor,
                'recent_replies': recent_replies,
                'total_replies': total_replies
            })

        return {
            'floors': floors_with_replies,
            'pagination': floors_pagination,
            'total_floors': floors_pagination.total
        }

    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '楼层ID', 'type': 'bigint', 'readonly': True},
            'post_id': {'label': '帖子ID', 'type': 'bigint'},
            'author_display': {'label': '楼主', 'type': 'string', 'readonly': True},
            'content': {'label': '楼层内容', 'type': 'text'},
            'floor_number': {'label': '楼层号', 'type': 'int', 'readonly': True},
            'like_count': {'label': '点赞次数', 'type': 'int', 'readonly': True},
            'reply_count': {'label': '回复次数', 'type': 'int', 'readonly': True},
            'status': {'label': '状态', 'type': 'enum', 'options': ['published', 'deleted']},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True},
            'updated_at': {'label': '更新时间', 'type': 'datetime', 'readonly': True}
        }

class ForumReply(db.Model):
    __tablename__ = 'forum_replies'
    __table_args__ = {'mysql_comment': '论坛回复表：存储对楼层的回复内容', 'comment': '论坛回复表：存储对楼层的回复内容'}
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='回复唯一标识')
    floor_id = db.Column(db.Integer, db.ForeignKey('forum_floors.id', ondelete='CASCADE'), nullable=False, comment='楼层ID')
    content = db.Column(db.Text, nullable=False, comment='回复内容')
    like_count = db.Column(db.Integer, default=0, comment='点赞次数')
    status = db.Column(db.Enum('published', 'deleted'), default='published', comment='回复状态')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    author_user_id = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='回复者用户ID（关联user_info.id，包含所有用户类型，用户注销后设为 NULL）')
    author_display = db.Column(db.String(80), nullable=False, default='用户已注销', comment='回复者显示名（用户注销后改为"用户已注销"）')

    quote_content = db.Column(db.Text, comment='引用的内容片段（可选）')
    quote_author = db.Column(db.String(80), comment='引用内容的作者（可选）')

    author_user = db.relationship('User', backref='forum_replies_authored', foreign_keys=[author_user_id])
    likes = db.relationship('ForumLike', backref='liked_reply', lazy='dynamic', cascade='all, delete-orphan', primaryjoin="and_(ForumReply.id==ForumLike.reply_id, ForumLike.target_type=='reply')")

    def update_author_display(self):
        
        if self.author_user_id and self.author_user and self.author_user.is_deleted == 0:
            if self.author_user.role == 'SUPER_ADMIN' or self.author_user.role == 'ADMIN':
                role_prefix = "管理员"
            elif self.author_user.role == 'ORG_USER':
                role_prefix = "组织用户"
            else:
                role_prefix = "用户"
            self.author_display = f"{self.author_user.username}（{role_prefix}）"
        else:
            self.author_display = "用户已注销"
            self.author_user_id = None

    @classmethod
    def create_reply(cls, floor_id, user_id, content, quote_content=None, quote_author=None):
        
        from . import db

        floor = ForumFloor.query.get(floor_id)
        if not floor:
            return None

        reply = cls(
            floor_id=floor_id,
            author_user_id=user_id,
            content=content,
            quote_content=quote_content,
            quote_author=quote_author
        )
        reply.update_author_display()

        db.session.add(reply)

        floor.reply_count += 1

        db.session.commit()
        return reply

    def delete_reply(self):
        
        from . import db

        if self.floor and self.floor.reply_count > 0:
            self.floor.reply_count -= 1

        db.session.delete(self)
        db.session.commit()

    def calculate_like_count(self):
        
        return ForumLike.query.filter_by(
            reply_id=self.id,
            target_type='reply'
        ).count()

    def update_counts(self):
        
        self.like_count = self.calculate_like_count()
        db.session.commit()

    @classmethod
    def get_replies_by_floor(cls, floor_id, page=1, per_page=20):
        
        from . import db

        replies_query = cls.query.filter_by(
            floor_id=floor_id,
            status='published'
        ).order_by(cls.created_at.asc())

        replies_pagination = replies_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

        return replies_pagination

    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '回复ID', 'type': 'bigint', 'readonly': True},
            'floor_id': {'label': '楼层ID', 'type': 'bigint'},
            'author_display': {'label': '回复者', 'type': 'string', 'readonly': True},
            'content': {'label': '回复内容', 'type': 'text'},
            'quote_content': {'label': '引用内容', 'type': 'text'},
            'quote_author': {'label': '引用作者', 'type': 'string'},
            'like_count': {'label': '点赞次数', 'type': 'int', 'readonly': True},
            'status': {'label': '状态', 'type': 'enum', 'options': ['published', 'deleted']},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True},
            'updated_at': {'label': '更新时间', 'type': 'datetime', 'readonly': True}
        }


class ForumVisit(db.Model):
    __tablename__ = 'forum_visits'
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='浏览记录ID（主键，自增）')
    post_id = db.Column(db.Integer, db.ForeignKey('forum_posts.id', ondelete='CASCADE'), nullable=False, comment='关联帖子ID（forum_posts表主键，级联删除）')
    user_id = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='CASCADE'), nullable=False, comment='浏览用户ID（关联user_info.id，包含所有用户类型）')
    first_visit_at = db.Column(db.DateTime, default=datetime.now, comment='首次浏览时间（记录创建时间戳）')
    last_visit_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='最后浏览时间（记录最后访问时间）')
    visit_count = db.Column(db.Integer, default=1, comment='该用户对此帖子的浏览次数')

    user = db.relationship('User', backref='forum_visits', foreign_keys=[user_id])

    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id', name='unique_forum_visit'),
        {'mysql_comment': '论坛浏览记录表：记录用户浏览帖子的历史', 'comment': '论坛浏览记录表：记录用户浏览帖子的历史'}
    )

    def increment_visit(self):
        
        self.visit_count += 1
        self.last_visit_at = datetime.now()
        db.session.commit()

    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '浏览记录ID', 'type': 'bigint', 'readonly': True},
            'post_id': {'label': '帖子ID', 'type': 'bigint'},
            'user_id': {'label': '用户ID', 'type': 'bigint'},
            'first_visit_at': {'label': '首次浏览时间', 'type': 'datetime', 'readonly': True},
            'last_visit_at': {'label': '最后浏览时间', 'type': 'datetime', 'readonly': True},
            'visit_count': {'label': '浏览次数', 'type': 'int', 'readonly': True}
        }


class ForumLike(db.Model):
    __tablename__ = 'forum_likes'
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='点赞唯一标识')
    target_type = db.Column(db.Enum('post', 'floor', 'reply'), nullable=False, comment='目标类型（post帖子/floor楼层/reply回复）')
    target_id = db.Column(db.Integer, nullable=False, comment='目标ID（对应帖子、楼层或回复的ID）')

    post_id = db.Column(db.Integer, db.ForeignKey('forum_posts.id', ondelete='CASCADE'), nullable=True, comment='关联帖子ID（仅当target_type为post时有值）')
    floor_id = db.Column(db.Integer, db.ForeignKey('forum_floors.id', ondelete='CASCADE'), nullable=True, comment='关联楼层ID（仅当target_type为floor时有值）')
    reply_id = db.Column(db.Integer, db.ForeignKey('forum_replies.id', ondelete='CASCADE'), nullable=True, comment='关联回复ID（仅当target_type为reply时有值）')

    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    user_id = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='CASCADE'), nullable=False, comment='点赞用户ID（关联user_info.id，包含所有用户类型）')
    user_display = db.Column(db.String(80), nullable=False, default='用户已注销', comment='点赞者显示名（用户注销后改为"用户已注销"）')

    user = db.relationship('User', backref='forum_likes', foreign_keys=[user_id])


    def update_user_display(self):
        
        if self.user_id and self.user and self.user.is_deleted == 0:
            if self.user.role == 'SUPER_ADMIN' or self.user.role == 'ADMIN':
                role_prefix = "管理员"
            elif self.user.role == 'ORG_USER':
                role_prefix = "组织用户"
            else:
                role_prefix = "用户"
            self.user_display = f"{self.user.username}（{role_prefix}）"
        else:
            self.user_display = "用户已注销"
            self.user_id = None

    @classmethod
    def create_like(cls, user_id, target_type, target_id, post_id=None, floor_id=None, reply_id=None):
        
        existing_like = cls.query.filter_by(
            user_id=user_id,
            target_type=target_type,
            target_id=target_id
        ).first()

        if existing_like:
            return None

        like = cls(
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            post_id=post_id if target_type == 'post' else None,
            floor_id=floor_id if target_type == 'floor' else None,
            reply_id=reply_id if target_type == 'reply' else None
        )

        from . import db
        db.session.add(like)

        if target_type == 'post' and post_id:
            post = ForumPost.query.get(post_id)
            if post:
                post.like_count += 1
        elif target_type == 'floor' and floor_id:
            floor = ForumFloor.query.get(floor_id)
            if floor:
                floor.like_count += 1
        elif target_type == 'reply' and reply_id:
            reply = ForumReply.query.get(reply_id)
            if reply:
                reply.like_count += 1

        db.session.commit()
        return like

    @classmethod
    def remove_like(cls, user_id, target_type, target_id, post_id=None, floor_id=None, reply_id=None):
        
        like = cls.query.filter_by(
            user_id=user_id,
            target_type=target_type,
            target_id=target_id
        ).first()

        if not like:
            return False

        from . import db
        db.session.delete(like)

        if target_type == 'post' and post_id:
            post = ForumPost.query.get(post_id)
            if post and post.like_count > 0:
                post.like_count -= 1
        elif target_type == 'floor' and floor_id:
            floor = ForumFloor.query.get(floor_id)
            if floor and floor.like_count > 0:
                floor.like_count -= 1
        elif target_type == 'reply' and reply_id:
            reply = ForumReply.query.get(reply_id)
            if reply and reply.like_count > 0:
                reply.like_count -= 1

        db.session.commit()
        return True

    __table_args__ = (
        db.UniqueConstraint('user_id', 'target_type', 'target_id', name='unique_forum_like'),
        {'mysql_comment': '论坛点赞表：记录用户对帖子、楼层和回复的点赞', 'comment': '论坛点赞表：记录用户对帖子、楼层和回复的点赞'}
    )

    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '点赞ID', 'type': 'bigint', 'readonly': True},
            'user_id': {'label': '用户ID', 'type': 'bigint'},
            'user_display': {'label': '点赞者', 'type': 'string', 'readonly': True},
            'target_type': {'label': '目标类型', 'type': 'enum', 'options': ['post', 'floor', 'reply']},
            'target_id': {'label': '目标ID', 'type': 'bigint'},
            'post_id': {'label': '帖子ID', 'type': 'bigint'},
            'floor_id': {'label': '楼层ID', 'type': 'bigint'},
            'reply_id': {'label': '回复ID', 'type': 'bigint'},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True}
        }