
from datetime import datetime
import logging
from .base import db, get_table_comment_args
from .user_models import User


class Notice(db.Model):
    __tablename__ = 'notice'
    __table_args__ = {'mysql_comment': '公告信息表：存储系统公告、通知和重要信息发布',
                     'comment': '公告信息表：存储系统公告、通知和重要信息发布'}
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='自增主键ID')
    release_time = db.Column(db.DateTime, nullable=False, default=datetime.now, comment='公告发布时间（自动使用服务器时间，不可变更）')
    update_time = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='公告更新时间')
    release_title = db.Column(db.String(150), nullable=False, comment='公告标题')
    release_notice = db.Column(db.Text, nullable=False, comment='公告内容')
    expiration = db.Column(db.DateTime, comment='公告到期时间')
    notice_type = db.Column(db.Enum('SYSTEM', 'ACTIVITY', 'GENERAL'), nullable=False, default='GENERAL', comment='公告类型（SYSTEM系统通知/ACTIVITY活动公告/GENERAL其他公告）')

    is_top = db.Column(db.Boolean, nullable=False, default=False, comment='是否置顶（置顶公告在列表中优先显示）')
    status = db.Column(db.Enum('DRAFT', 'PENDING', 'APPROVED', 'REJECTED', 'EXPIRED'), nullable=False, default='DRAFT', comment='公告状态（DRAFT草稿/PENDING待审核/APPROVED已发布/REJECTED已拒绝/EXPIRED已到期）')
    is_expired = db.Column(db.Boolean, nullable=False, default=False, comment='是否已到期（根据当前时间和expiration字段自动判断）')
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='审核人ID（关联user_info.id，审核该公告的管理员ID）')
    reviewed_at = db.Column(db.DateTime, comment='审核时间（管理员审核公告的时间戳）')
    review_comment = db.Column(db.Text, comment='审核意见（管理员审核时填写的意见或说明）')

    author_user_id = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='发布者用户ID（关联user_info.id，用户注销后设为 NULL）')
    author_display = db.Column(db.String(80), nullable=False, default='系统发布', comment='发布者显示名（用户注销后改为"用户已注销"）')

    author_user = db.relationship('User', backref='notices_published', foreign_keys=[author_user_id])
    reviewer = db.relationship('User', backref='notices_reviewed', foreign_keys=[reviewed_by])
    attachments = db.relationship('NoticeAttachment', backref='notice', cascade='all, delete-orphan')

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
            self.author_display = "系统发布"
            self.author_user_id = None

    def check_expiration(self):
        
        current_utc = datetime.utcnow()
        if self.expiration and current_utc >= self.expiration:
            if not self.is_expired or self.status != 'EXPIRED':
                self.is_expired = True
                self.status = 'EXPIRED'
        else:
            if self.is_expired:
                self.is_expired = False
                if self.status == 'EXPIRED':
                    self.status = 'APPROVED'

    def submit_for_review(self):
        
        if self.status == 'DRAFT':
            self.status = 'PENDING'
            return True
        return False

    def approve(self, reviewer_user_id, comment=None):
        
        if self.status == 'PENDING':
            self.status = 'APPROVED'
            self.reviewed_by = reviewer_user_id
            self.reviewed_at = datetime.now()
            self.review_comment = comment
            self.check_expiration()
            return True
        return False

    def reject(self, reviewer_user_id, comment):
        
        if self.status == 'PENDING':
            self.status = 'REJECTED'
            self.reviewed_by = reviewer_user_id
            self.reviewed_at = datetime.now()
            self.review_comment = comment
            return True
        return False

    def is_active(self):
        
        self.check_expiration()
        return self.status == 'APPROVED' and not self.is_expired

    def anonymize_related_reads_on_deletion(self):
        
        try:
            notice_reads = NoticeRead.query.filter_by(notice_id=self.id).all()
            for notice_read in notice_reads:
                notice_read.anonymize_for_notice_deletion()

            logger = logging.getLogger(__name__)
            logger.info(f"【公告删除匿名化完成】公告ID: {self.id}, 匿名化已读记录数: {len(notice_reads)}")

        except Exception:
            logger = logging.getLogger(__name__)
            logger.exception(f"【公告删除匿名化异常】公告ID: {self.id}")

    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '公告ID', 'type': 'bigint', 'readonly': True},
            'release_time': {'label': '发布时间', 'type': 'datetime', 'readonly': True},
            'update_time': {'label': '更新时间', 'type': 'datetime', 'readonly': True},
            'release_title': {'label': '公告标题', 'type': 'string'},
            'release_notice': {'label': '公告内容', 'type': 'string'},
            'expiration': {'label': '到期时间', 'type': 'datetime'},
            'notice_type': {'label': '公告类型', 'type': 'enum', 'options': ['SYSTEM', 'ACTIVITY', 'GENERAL']},
            'is_top': {'label': '是否置顶', 'type': 'boolean'},
            'status': {'label': '公告状态', 'type': 'enum', 'options': ['DRAFT', 'PENDING', 'APPROVED', 'REJECTED', 'EXPIRED']},
            'is_expired': {'label': '是否已到期', 'type': 'boolean', 'readonly': True},
            'reviewed_by': {'label': '审核人ID', 'type': 'bigint', 'readonly': True},
            'reviewed_at': {'label': '审核时间', 'type': 'datetime', 'readonly': True},
            'review_comment': {'label': '审核意见', 'type': 'text', 'readonly': True},
            'author_display': {'label': '发布者', 'type': 'string', 'readonly': True},
            'attachments': {'label': '附件', 'type': 'relation', 'relation_model': 'NoticeAttachment'}
        }


class NoticeAttachment(db.Model):
    __tablename__ = 'notice_attachments'
    __table_args__ = {'mysql_comment': '公告附件表：存储公告相关的文件附件信息',
                     'comment': '公告附件表：存储公告相关的文件附件信息'}
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='附件记录ID（主键，自增）')
    notice_id = db.Column(db.Integer, db.ForeignKey('notice.id', ondelete='CASCADE'), nullable=False, comment='关联公告ID（notice表主键，级联删除）')
    uploader_account = db.Column(db.String(80), db.ForeignKey('user_info.account'), nullable=False, comment='上传者账号（关联user_info.account）')
    file_name = db.Column(db.String(255), nullable=False, comment='附件文件名（包含扩展名）')
    file_path = db.Column(db.String(500), nullable=False, comment='附件存储路径（相对于 uploads/notice/ 的相对路径）')
    file_size = db.Column(db.BigInteger, nullable=False, comment='附件文件大小（字节）')
    file_type = db.Column(db.String(50), nullable=False, comment='附件文件类型（MIME类型或文件扩展名）')
    upload_time = db.Column(db.DateTime, default=datetime.now, comment='附件上传时间（记录创建时间戳）')

    uploader = db.relationship('User', backref='notice_attachments_uploaded', foreign_keys=[uploader_account])

    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '附件ID', 'type': 'bigint', 'readonly': True},
            'notice_id': {'label': '关联公告ID', 'type': 'bigint', 'readonly': True},
            'uploader_account': {'label': '上传者账号', 'type': 'string'},
            'file_name': {'label': '文件名', 'type': 'string'},
            'file_path': {'label': '文件路径', 'type': 'string'},
            'file_size': {'label': '文件大小', 'type': 'bigint'},
            'file_type': {'label': '文件类型', 'type': 'string'},
            'upload_time': {'label': '上传时间', 'type': 'datetime', 'readonly': True}
        }


class NoticeRead(db.Model):
    __tablename__ = 'notice_read'
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='已读记录ID（主键，自增）')
    user_id = db.Column(db.Integer, db.ForeignKey('user_info.id', ondelete='SET NULL'), nullable=True, comment='用户ID（关联user_info.id，用户删除时设为 NULL）')
    notice_id = db.Column(db.Integer, db.ForeignKey('notice.id', ondelete='SET NULL'), nullable=True, comment='公告ID（关联notice.id，公告删除时设为 NULL）')
    read_time = db.Column(db.DateTime, default=datetime.now, comment='阅读时间（记录用户阅读公告的时间戳）')

    is_anonymized = db.Column(db.Boolean, nullable=False, default=False, comment='是否已匿名化（用户注销或公告删除时）')
    anonymized_user_display = db.Column(db.String(80), nullable=True, comment='匿名化后的用户显示名')
    anonymized_user_account = db.Column(db.String(80), nullable=True, comment='原始用户账号（用于统计和审计）')
    anonymized_user_role = db.Column(db.String(20), nullable=True, comment='匿名化时的用户角色')
    anonymized_at = db.Column(db.DateTime, nullable=True, comment='匿名化时间')
    anonymize_reason = db.Column(db.String(50), nullable=True, comment='匿名化原因：user_delete/notice_delete/other')

    user = db.relationship('User', backref='notice_reads', foreign_keys=[user_id])
    notice = db.relationship('Notice', backref='reads', foreign_keys=[notice_id])

    __table_args__ = (
        db.UniqueConstraint('user_id', 'notice_id', name='unique_user_notice_read'),
        {'mysql_comment': '公告已读记录表：记录用户阅读公告的状态和时间',
         'comment': '公告已读记录表：记录用户阅读公告的状态和时间'}
    )

    def anonymize_for_user_deletion(self):
        
        if not self.is_anonymized and self.user:
            self.anonymized_user_account = self.user.account
            self.anonymized_user_role = self.user.role

            self.anonymized_user_display = "用户已注销"
            self.user_id = None
            self.is_anonymized = True
            self.anonymized_at = datetime.now()
            self.anonymize_reason = 'user_delete'

            logger = logging.getLogger(__name__)
            logger.info(f"【公告已读记录匿名化】用户: {self.anonymized_user_account}, 公告ID: {self.notice_id}")

    def anonymize_for_notice_deletion(self):
        
        if not self.is_anonymized:
            notice_info = f"公告ID:{self.notice_id}" if self.notice_id else "未知公告"

            self.anonymized_user_display = "公告已删除"
            self.notice_id = None
            self.is_anonymized = True
            self.anonymized_at = datetime.now()
            self.anonymize_reason = 'notice_delete'

            logger = logging.getLogger(__name__)
            logger.info(f"【公告删除匿名化】{notice_info}, 用户: {self.anonymized_user_account}")

    def get_effective_user_display(self):
        
        if self.is_anonymized:
            return self.anonymized_user_display or "未知用户"
        elif self.user:
            return self.user.username
        else:
            return "系统用户"

    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '已读记录ID', 'type': 'bigint', 'readonly': True},
            'user_id': {'label': '用户ID', 'type': 'bigint', 'readonly': True},
            'notice_id': {'label': '公告ID', 'type': 'bigint', 'readonly': True},
            'read_time': {'label': '阅读时间', 'type': 'datetime', 'readonly': True},
            'is_anonymized': {'label': '是否已匿名化', 'type': 'boolean', 'readonly': True},
            'anonymized_user_display': {'label': '匿名化用户显示', 'type': 'string', 'readonly': True},
            'anonymized_user_account': {'label': '原始用户账号', 'type': 'string', 'readonly': True},
            'anonymized_user_role': {'label': '匿名化用户角色', 'type': 'string', 'readonly': True},
            'anonymized_at': {'label': '匿名化时间', 'type': 'datetime', 'readonly': True},
            'anonymize_reason': {'label': '匿名化原因', 'type': 'string', 'readonly': True}
        }