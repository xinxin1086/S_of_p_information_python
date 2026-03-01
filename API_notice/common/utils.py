# API_notice公共工具函数
# 包含公告模块的公共工具：已读统计、推送规则、权限校验等
# 时间策略：所有时间均使用 UTC naive datetime（datetime.utcnow()），确保全局一致性

from datetime import datetime
import logging
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import and_, or_, func, text
from components import db
from components.models.notice_models import Notice, NoticeRead, NoticeAttachment
from components.models.user_models import User, Admin


class NoticeUtils:
    """公告模块公共工具类"""

    @staticmethod
    def get_user_unread_count(user_id: int, is_admin: bool = False) -> int:
        """
        高效查询用户未读公告数量（避免全表扫描）

        Args:
            user_id: 用户ID
            is_admin: 是否为管理员

        Returns:
            int: 未读公告数量
        """
        try:
            # 查询用户已读的公告ID列表
            read_notice_ids = db.session.query(NoticeRead.notice_id).filter(
                NoticeRead.user_id == user_id
            ).subquery()

            # 查询活跃公告（已发布且未到期）
            active_notices_query = Notice.query.filter(
                and_(
                    Notice.status == 'APPROVED',
                    or_(Notice.expiration.is_(None), Notice.expiration > datetime.utcnow()),
                    ~Notice.id.in_(read_notice_ids)
                )
            )

            # 根据公告类型过滤
            if is_admin:
                # 管理员可以看到所有类型的公告
                pass
            else:
                # 普通用户可以看到所有公告类型（SYSTEM/ACTIVITY/GENERAL）
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
        """
        获取带未读状态的用户公告列表（置顶公告优先展示）

        Args:
            user_id: 用户ID
            page: 页码
            size: 页大小
            notice_type: 公告类型筛选
            is_admin: 是否为管理员

        Returns:
            Dict: 包含分页信息和公告列表
        """
        try:
            # 查询用户已读的公告ID列表
            read_notice_ids = db.session.query(NoticeRead.notice_id).filter(
                NoticeRead.user_id == user_id
            ).subquery()

            # 构建基础查询：活跃公告（已发布且未到期）
            base_query = Notice.query.filter(
                and_(
                    Notice.status == 'APPROVED',
                    or_(Notice.expiration.is_(None), Notice.expiration > datetime.utcnow())
                )
            )

            # 根据用户类型过滤公告类型
            if not is_admin:
                base_query = base_query.filter(
                    Notice.notice_type.in_(['SYSTEM', 'ACTIVITY', 'GENERAL'])
                )

            # 按类型筛选
            if notice_type:
                base_query = base_query.filter(Notice.notice_type == notice_type)

            # 按置顶状态和发布时间排序：置顶优先，然后按发布时间倒序
            paginated_query = base_query.order_by(
                Notice.is_top.desc(),
                Notice.release_time.desc()
            )

            # 分页查询
            pagination = paginated_query.paginate(page=page, per_page=size, error_out=False)
            notices = pagination.items
            total = pagination.total

            # 构建返回数据
            notice_list = []
            for notice in notices:
                # 检查是否已读
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
                    'is_top': getattr(notice, 'is_top', False),  # 如果没有is_top字段，默认为False
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
        """
        标记公告为已读

        Args:
            user_id: 用户ID
            notice_id: 公告ID

        Returns:
            bool: 是否成功标记
        """
        try:
            # 检查公告是否存在且为活跃状态
            notice = Notice.query.filter(
                and_(
                    Notice.id == notice_id,
                    Notice.status == 'APPROVED',
                    or_(Notice.expiration.is_(None), Notice.expiration > datetime.utcnow())
                )
            ).first()

            if not notice:
                return False

            # 检查是否已经标记为已读
            existing_read = NoticeRead.query.filter(
                and_(
                    NoticeRead.user_id == user_id,
                    NoticeRead.notice_id == notice_id
                )
            ).first()

            if existing_read:
                return True  # 已经标记过了

            # 创建新的已读记录
            notice_read = NoticeRead(
                user_id=user_id,
                notice_id=notice_id,
                read_time=datetime.utcnow()  # 使用 UTC 时间
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
        """
        标记所有公告为已读

        Args:
            user_id: 用户ID
            is_admin: 是否为管理员

        Returns:
            int: 标记为已读的公告数量
        """
        try:
            # 获取用户未读的活跃公告
            read_notice_ids = db.session.query(NoticeRead.notice_id).filter(
                NoticeRead.user_id == user_id
            ).subquery()

            # 查询未读的活跃公告
            unread_notices_query = Notice.query.filter(
                and_(
                    Notice.status == 'APPROVED',
                    or_(Notice.expiration.is_(None), Notice.expiration > datetime.utcnow()),
                    ~Notice.id.in_(read_notice_ids)
                )
            )

            # 根据用户类型过滤公告类型
            if not is_admin:
                unread_notices_query = unread_notices_query.filter(
                    Notice.notice_type.in_(['SYSTEM', 'ACTIVITY', 'GENERAL'])
                )

            unread_notices = unread_notices_query.all()

            # 批量创建已读记录
            read_count = 0
            for notice in unread_notices:
                notice_read = NoticeRead(
                    user_id=user_id,
                    notice_id=notice.id,
                    read_time=datetime.utcnow()  # 使用 UTC 时间
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
        """
        获取公告已读人数统计

        Args:
            notice_id: 公告ID

        Returns:
            Dict: 统计信息
        """
        try:
            # 检查公告是否存在
            notice = Notice.query.get(notice_id)
            if not notice:
                return None

            # 统计已读人数
            read_count = NoticeRead.query.filter(
                NoticeRead.notice_id == notice_id
            ).count()

            # 获取用户总数（普通用户+管理员）
            user_count = User.query.filter(User.is_deleted == 0).count()
            admin_count = Admin.query.count()
            total_target_count = user_count + admin_count

            # 根据公告类型计算目标用户数
            # 兼容旧数据：若存在 'ADMIN' 类型则仍视为仅管理员目标
            if notice.notice_type == 'ADMIN':
                target_count = admin_count
            elif notice.notice_type == 'SYSTEM':
                target_count = total_target_count
            elif notice.notice_type in ('ACTIVITY', 'GENERAL'):
                target_count = user_count
            else:
                # 非预期类型，默认以普通用户为目标
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
    """公告权限校验工具类"""

    @staticmethod
    def can_user_view_notice(user_id: int, notice_id: int, is_admin: bool = False) -> Tuple[bool, str]:
        """
        检查用户是否有权限查看指定公告

        Args:
            user_id: 用户ID
            notice_id: 公告ID
            is_admin: 是否为管理员

        Returns:
            Tuple[bool, str]: (是否有权限, 错误信息)
        """
        try:
            notice = Notice.query.get(notice_id)
            if not notice:
                return False, "公告不存在"

            # 检查公告状态
            if notice.status != 'APPROVED':
                return False, "公告未发布"

            # 检查公告是否已过期
            if notice.expiration and notice.expiration <= datetime.utcnow():
                return False, "公告已过期"

            # 检查公告类型权限
            if not is_admin and notice.notice_type not in ['SYSTEM', 'ACTIVITY', 'GENERAL']:
                return False, "无权限查看此类型公告"

            return True, ""

        except Exception:
            logger = logging.getLogger(__name__)
            logger.exception("【查看权限校验异常】")
            return False, "权限校验失败"

    @staticmethod
    def can_admin_manage_notice(admin_user_id: int, notice: Notice) -> Tuple[bool, str]:
        """
        检查管理员是否有权限管理指定公告

        Args:
            admin_user_id: 管理员用户ID
            notice: 公告对象

        Returns:
            Tuple[bool, str]: (是否有权限, 错误信息)
        """
        try:
            # 检查是否为公告作者
            if notice.author_user_id != admin_user_id:
                return False, "无权限编辑他人发布的公告"

            # 检查公告状态（某些状态下不允许编辑）
            if notice.status == 'EXPIRED':
                return False, "已过期的公告不允许编辑"

            return True, ""

        except Exception:
            logger = logging.getLogger(__name__)
            logger.exception("【管理权限校验异常】")
            return False, "权限校验失败"

    @staticmethod
    def validate_notice_access_scope(notice_type: str, target_user_type: str) -> bool:
        """
        验证公告推送范围是否有效

        Args:
            notice_type: 公告类型 (SYSTEM/ACTIVITY/GENERAL)
            target_user_type: 目标用户类型 ('ALL', 'USER')

        Returns:
            bool: 推送范围是否有效
        """
        # 系统通知可以推送给所有人
        if notice_type == 'SYSTEM':
            return target_user_type in ['ALL', 'USER']

        # 活动公告和其他公告只能推送给普通用户或所有人
        if notice_type in ['ACTIVITY', 'GENERAL'] and target_user_type not in ['USER', 'ALL']:
            return False

        return True


class NoticeQueryUtils:
    """公告查询工具类"""

    @staticmethod
    def build_admin_filter_query(base_query, status_filter: Optional[str] = None,
                                type_filter: Optional[str] = None,
                                date_from: Optional[str] = None,
                                date_to: Optional[str] = None,
                                author_filter: Optional[str] = None):
        """
        为管理员构建带筛选条件的公告查询

        Args:
            base_query: 基础查询对象
            status_filter: 状态筛选
            type_filter: 类型筛选
            date_from: 开始日期
            date_to: 结束日期
            author_filter: 作者筛选

        Returns:
            查询对象
        """
        try:
            # 状态筛选
            if status_filter:
                base_query = base_query.filter(Notice.status == status_filter)

            # 类型筛选
            if type_filter:
                base_query = base_query.filter(Notice.notice_type == type_filter)

            # 日期范围筛选
            if date_from:
                try:
                    date_from_obj = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                    base_query = base_query.filter(Notice.release_time >= date_from_obj)
                except ValueError:
                    pass  # 忽略无效的日期格式

            if date_to:
                try:
                    date_to_obj = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                    base_query = base_query.filter(Notice.release_time <= date_to_obj)
                except ValueError:
                    pass  # 忽略无效的日期格式

            # 作者筛选
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
        """
        获取公告详情（包含附件信息）

        Args:
            notice_id: 公告ID

        Returns:
            Dict: 公告详情信息
        """
        try:
            notice = Notice.query.get(notice_id)
            if not notice:
                return None

            # 构建附件信息
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


# 导出工具类
__all__ = [
    'NoticeUtils',
    'NoticePermissionUtils',
    'NoticeQueryUtils'
]