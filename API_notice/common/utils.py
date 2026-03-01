
from datetime import datetime
import logging
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import and_, or_, func, text
from components import db
from components.models.notice_models import Notice, NoticeRead, NoticeAttachment
from components.models.user_models import User, Admin


class NoticeUtils:
    

    @staticmethod
    def get_user_unread_count(user_id: int, is_admin: bool = False) -> int:
        
        try:
            read_notice_ids = db.session.query(NoticeRead.notice_id).filter(
                NoticeRead.user_id == user_id
            ).subquery()

            active_notices_query = Notice.query.filter(
                and_(
                    Notice.status == 'APPROVED',
                    or_(Notice.expiration.is_(None), Notice.expiration > datetime.utcnow()),
                    ~Notice.id.in_(read_notice_ids)
                )
            )

            if is_admin:
                pass
            else:
                active_notices_query = active_notices_query.filter(
                    Notice.notice_type.in_(['SYSTEM', 'ACTIVITY', 'GENERAL'])
                )

            return active_notices_query.count()

        except Exception:
            logger = logging.getLogger(__name__)
            logger.exception("【未读公告统计异常】")
            return 0

    @staticmethod
    def get_user_notice_list(user_id: int, page: int = 1, size: int = 10,
                           notice_type: Optional[str] = None,
                           is_admin: bool = False) -> Dict[str, Any]:
        
        try:
            read_notice_ids = db.session.query(NoticeRead.notice_id).filter(
                NoticeRead.user_id == user_id
            ).subquery()

            base_query = Notice.query.filter(
                and_(
                    Notice.status == 'APPROVED',
                    or_(Notice.expiration.is_(None), Notice.expiration > datetime.utcnow())
                )
            )

            if not is_admin:
                base_query = base_query.filter(
                    Notice.notice_type.in_(['SYSTEM', 'ACTIVITY', 'GENERAL'])
                )

            if notice_type:
                base_query = base_query.filter(Notice.notice_type == notice_type)

            paginated_query = base_query.order_by(
                Notice.is_top.desc(),
                Notice.release_time.desc()
            )

            pagination = paginated_query.paginate(page=page, per_page=size, error_out=False)
            notices = pagination.items
            total = pagination.total

            notice_list = []
            for notice in notices:
                is_read = db.session.query(NoticeRead).filter(
                    and_(
                        NoticeRead.user_id == user_id,
                        NoticeRead.notice_id == notice.id
                    )
                ).first() is not None

                notice_data = {
                    'id': notice.id,
                    'title': notice.release_title,
                    'content': notice.release_notice[:200] + '...' if len(notice.release_notice) > 200 else notice.release_notice,
                    'notice_type': notice.notice_type,
                    'is_top': getattr(notice, 'is_top', False),
                    'release_time': notice.release_time.isoformat().replace('+00:00', 'Z'),
                    'expiration': notice.expiration.isoformat().replace('+00:00', 'Z') if notice.expiration else None,
                    'author_display': notice.author_display,
                    'is_read': is_read,
                    'attachment_count': len(notice.attachments) if notice.attachments else 0
                }
                notice_list.append(notice_data)

            return {
                'total': total,
                'page': page,
                'size': size,
                'items': notice_list,
                'unread_count': NoticeUtils.get_user_unread_count(user_id, is_admin)
            }

        except Exception:
            logger = logging.getLogger(__name__)
            logger.exception("【公告列表查询异常】")
            return {
                'total': 0,
                'page': page,
                'size': size,
                'items': [],
                'unread_count': 0
            }

    @staticmethod
    def mark_notice_as_read(user_id: int, notice_id: int) -> bool:
        
        try:
            notice = Notice.query.filter(
                and_(
                    Notice.id == notice_id,
                    Notice.status == 'APPROVED',
                    or_(Notice.expiration.is_(None), Notice.expiration > datetime.utcnow())
                )
            ).first()

            if not notice:
                return False

            existing_read = NoticeRead.query.filter(
                and_(
                    NoticeRead.user_id == user_id,
                    NoticeRead.notice_id == notice_id
                )
            ).first()

            if existing_read:
                return True

            notice_read = NoticeRead(
                user_id=user_id,
                notice_id=notice_id,
                read_time=datetime.utcnow()
            )

            db.session.add(notice_read)
            db.session.commit()

            return True

        except Exception:
            db.session.rollback()
            logger = logging.getLogger(__name__)
            logger.exception("【标记已读异常】")
            return False

    @staticmethod
    def mark_all_notices_as_read(user_id: int, is_admin: bool = False) -> int:
        
        try:
            read_notice_ids = db.session.query(NoticeRead.notice_id).filter(
                NoticeRead.user_id == user_id
            ).subquery()

            unread_notices_query = Notice.query.filter(
                and_(
                    Notice.status == 'APPROVED',
                    or_(Notice.expiration.is_(None), Notice.expiration > datetime.utcnow()),
                    ~Notice.id.in_(read_notice_ids)
                )
            )

            if not is_admin:
                unread_notices_query = unread_notices_query.filter(
                    Notice.notice_type.in_(['SYSTEM', 'ACTIVITY', 'GENERAL'])
                )

            unread_notices = unread_notices_query.all()

            read_count = 0
            for notice in unread_notices:
                notice_read = NoticeRead(
                    user_id=user_id,
                    notice_id=notice.id,
                    read_time=datetime.utcnow()
                )
                db.session.add(notice_read)
                read_count += 1

            db.session.commit()
            return read_count

        except Exception:
            db.session.rollback()
            logger = logging.getLogger(__name__)
            logger.exception("【全部标记已读异常】")
            return 0

    @staticmethod
    def get_notice_read_statistics(notice_id: int) -> Dict[str, Any]:
        
        try:
            notice = Notice.query.get(notice_id)
            if not notice:
                return None

            read_count = NoticeRead.query.filter(
                NoticeRead.notice_id == notice_id
            ).count()

            user_count = User.query.filter(User.is_deleted == 0).count()
            admin_count = Admin.query.count()
            total_target_count = user_count + admin_count

            if notice.notice_type == 'ADMIN':
                target_count = admin_count
            elif notice.notice_type == 'SYSTEM':
                target_count = total_target_count
            elif notice.notice_type in ('ACTIVITY', 'GENERAL'):
                target_count = user_count
            else:
                target_count = user_count

            read_rate = (read_count / target_count * 100) if target_count > 0 else 0

            return {
                'notice_id': notice_id,
                'notice_title': notice.release_title,
                'notice_type': notice.notice_type,
                'target_user_count': target_count,
                'read_count': read_count,
                'unread_count': target_count - read_count,
                'read_rate': round(read_rate, 2)
            }

        except Exception:
            logger = logging.getLogger(__name__)
            logger.exception("【已读统计异常】")
            return None


class NoticePermissionUtils:
    

    @staticmethod
    def can_user_view_notice(user_id: int, notice_id: int, is_admin: bool = False) -> Tuple[bool, str]:
        
        try:
            notice = Notice.query.get(notice_id)
            if not notice:
                return False, "公告不存在"

            if notice.status != 'APPROVED':
                return False, "公告未发布"

            if notice.expiration and notice.expiration <= datetime.utcnow():
                return False, "公告已过期"

            if not is_admin and notice.notice_type not in ['SYSTEM', 'ACTIVITY', 'GENERAL']:
                return False, "无权限查看此类型公告"

            return True, ""

        except Exception:
            logger = logging.getLogger(__name__)
            logger.exception("【查看权限校验异常】")
            return False, "权限校验失败"

    @staticmethod
    def can_admin_manage_notice(admin_user_id: int, notice: Notice) -> Tuple[bool, str]:
        
        try:
            if notice.author_user_id != admin_user_id:
                return False, "无权限编辑他人发布的公告"

            if notice.status == 'EXPIRED':
                return False, "已过期的公告不允许编辑"

            return True, ""

        except Exception:
            logger = logging.getLogger(__name__)
            logger.exception("【管理权限校验异常】")
            return False, "权限校验失败"

    @staticmethod
    def validate_notice_access_scope(notice_type: str, target_user_type: str) -> bool:
        
        if notice_type == 'SYSTEM':
            return target_user_type in ['ALL', 'USER']

        if notice_type in ['ACTIVITY', 'GENERAL'] and target_user_type not in ['USER', 'ALL']:
            return False

        return True


class NoticeQueryUtils:
    

    @staticmethod
    def build_admin_filter_query(base_query, status_filter: Optional[str] = None,
                                type_filter: Optional[str] = None,
                                date_from: Optional[str] = None,
                                date_to: Optional[str] = None,
                                author_filter: Optional[str] = None):
        
        try:
            if status_filter:
                base_query = base_query.filter(Notice.status == status_filter)

            if type_filter:
                base_query = base_query.filter(Notice.notice_type == type_filter)

            if date_from:
                try:
                    date_from_obj = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                    base_query = base_query.filter(Notice.release_time >= date_from_obj)
                except ValueError:
                    pass

            if date_to:
                try:
                    date_to_obj = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                    base_query = base_query.filter(Notice.release_time <= date_to_obj)
                except ValueError:
                    pass

            if author_filter:
                base_query = base_query.filter(
                    Notice.author_display.like(f"%{author_filter}%")
                )

            return base_query

        except Exception:
            logger = logging.getLogger(__name__)
            logger.exception("【查询筛选构建异常】")
            return base_query

    @staticmethod
    def get_notice_with_attachments(notice_id: int) -> Optional[Dict[str, Any]]:
        
        try:
            notice = Notice.query.get(notice_id)
            if not notice:
                return None

            attachments = []
            if notice.attachments:
                for attachment in notice.attachments:
                    attachment_data = {
                        'id': attachment.id,
                        'file_name': attachment.file_name,
                        'file_path': attachment.file_path,
                        'file_size': attachment.file_size,
                        'file_type': attachment.file_type,
                        'upload_time': attachment.upload_time.isoformat().replace('+00:00', 'Z'),
                        'uploader_account': attachment.uploader_account
                    }
                    attachments.append(attachment_data)

            return {
                'id': notice.id,
                'title': notice.release_title,
                'content': notice.release_notice,
                'notice_type': notice.notice_type,
                'status': notice.status,
                'is_top': getattr(notice, 'is_top', False),
                'release_time': notice.release_time.isoformat().replace('+00:00', 'Z'),
                'update_time': notice.update_time.isoformat().replace('+00:00', 'Z'),
                'expiration': notice.expiration.isoformat().replace('+00:00', 'Z') if notice.expiration else None,
                'author_display': notice.author_display,
                'author_user_id': notice.author_user_id,
                'reviewed_by': notice.reviewed_by,
                'reviewed_at': notice.reviewed_at.isoformat().replace('+00:00', 'Z') if notice.reviewed_at else None,
                'review_comment': notice.review_comment,
                'is_expired': notice.is_expired,
                'attachments': attachments
            }

        except Exception:
            logger = logging.getLogger(__name__)
            logger.exception("【公告详情查询异常】")
            return None


__all__ = [
    'NoticeUtils',
    'NoticePermissionUtils',
    'NoticeQueryUtils'
]