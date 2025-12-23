# 其他相关模型

from datetime import datetime
from .base import db
from .user_models import User


# 附件模型（对应attachments表）
class Attachment(db.Model):
    __tablename__ = 'attachments'
    __table_args__ = {'mysql_comment': '附件信息表：存储系统中的文件附件信息', 'comment': '附件信息表：存储系统中的文件附件信息'}
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='附件唯一标识')
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