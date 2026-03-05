# API_notice 模块 - 统一路由文件
# 本文件整合了所有公告相关的路由和工具类
# 原始文件结构:
#   - common/utils.py (工具类)
#   - notice/category.py (公告分类管理)
#   - notice/public.py (公开访问接口)
#   - user/notice_ops.py (用户操作)
#   - admin/notice_manage.py (管理员管理)

# ==============================================================================
# 1. 导入语句
# ==============================================================================

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from components import db, token_required
from components.models.notice_models import Notice, NoticeRead, NoticeAttachment
from components.models.user_models import User, Admin
from components.response_service import ResponseService
from sqlalchemy import and_, or_, func
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)


# ==============================================================================
# 2. 工具类 (原 common/utils.py)
# ==============================================================================

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
                return True

            # 创建新的已读记录
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
                    read_time=datetime.utcnow()
                )
                db.session.add(notice_read)
                read_count += 1

            db.session.commit()
            return read_count

        except Exception:
            db.session.rollback()
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
                    pass

            if date_to:
                try:
                    date_to_obj = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                    base_query = base_query.filter(Notice.release_time <= date_to_obj)
                except ValueError:
                    pass

            # 作者筛选
            if author_filter:
                base_query = base_query.filter(
                    Notice.author_display.like(f"%{author_filter}%")
                )

            return base_query

        except Exception:
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
            logger.exception("【公告详情查询异常】")
            return None


# ==============================================================================
# 3. 辅助装饰器
# ==============================================================================

def admin_required(f):
    """管理员权限验证装饰器"""
    def decorated_function(current_user, *args, **kwargs):
        # 检查当前用户是否为管理员
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        if not current_admin:
            return jsonify({
                'success': False,
                'message': '需要管理员权限',
                'data': None
            }), 403
        return f(current_user, *args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


# ==============================================================================
# 4. 蓝图创建和路由注册
# ==============================================================================

# ------------------------------------------------------------------------------
# 4.1 bp_notice_category - 公告分类管理 (原 notice/category.py)
# ------------------------------------------------------------------------------

bp_notice_category = Blueprint('notice_category', __name__, url_prefix='/api/notice')


# 公告类型配置
NOTICE_TYPES = {
    'SYSTEM': {
        'name': '系统通知',
        'description': '系统级重要通知，所有用户可见',
        'color': '#ff4d4f',
        'icon': 'system',
        'target_users': ['ALL'],
        'priority': 1
    },
    'ACTIVITY': {
        'name': '活动公告',
        'description': '活动类公告，普通用户可见',
        'color': '#faad14',
        'icon': 'activity',
        'target_users': ['USER'],
        'priority': 2
    },
    'GENERAL': {
        'name': '其他公告',
        'description': '其他类型的公告，普通用户可见',
        'color': '#52c41a',
        'icon': 'general',
        'target_users': ['USER'],
        'priority': 3
    }
}


# 公告模板配置
NOTICE_TEMPLATES = [
    {
        'id': 'system_maintenance',
        'name': '系统维护公告',
        'type': 'SYSTEM',
        'template': '''系统维护公告

尊敬的用户：

为了提供更好的服务，我们将进行系统维护，具体安排如下：

维护时间：{maintenance_time}
维护范围：{maintenance_scope}
影响内容：{impact_content}

维护期间，相关服务将暂时无法访问。给您带来的不便，敬请谅解。

如有疑问，请联系：
技术支持：{support_contact}
服务热线：{service_hotline}

感谢您的理解与支持！

{company_name}
{date}''',
        'variables': [
            {'name': 'maintenance_time', 'label': '维护时间', 'required': True},
            {'name': 'maintenance_scope', 'label': '维护范围', 'required': True},
            {'name': 'impact_content', 'label': '影响内容', 'required': True},
            {'name': 'support_contact', 'label': '技术支持', 'required': False},
            {'name': 'service_hotline', 'label': '服务热线', 'required': False},
            {'name': 'company_name', 'label': '公司名称', 'required': True},
            {'name': 'date', 'label': '公告日期', 'required': True}
        ]
    },
    {
        'id': 'feature_update',
        'name': '功能更新公告',
        'type': 'GENERAL',
        'template': '''功能更新公告

亲爱的用户：

我们很高兴地通知您，系统已进行功能更新，新增/优化了以下功能：

【新增功能】
{new_features}

【功能优化】
{improved_features}

【问题修复】
{fixed_issues}

更新时间：{update_time}
版本号：{version_number}

欢迎体验新功能，如有任何问题或建议，请及时反馈。

感谢您的支持！

{company_name}
{date}''',
        'variables': [
            {'name': 'new_features', 'label': '新增功能', 'required': False},
            {'name': 'improved_features', 'label': '功能优化', 'required': False},
            {'name': 'fixed_issues', 'label': '问题修复', 'required': False},
            {'name': 'update_time', 'label': '更新时间', 'required': True},
            {'name': 'version_number', 'label': '版本号', 'required': True},
            {'name': 'company_name', 'label': '公司名称', 'required': True},
            {'name': 'date', 'label': '公告日期', 'required': True}
        ]
    },
    {
        'id': 'holiday_notice',
        'name': '节假日通知',
        'type': 'GENERAL',
        'template': '''节假日通知

各位用户：

根据国家法定节假日安排，现将{holiday_name}假期安排通知如下：

【放假时间】
{holiday_period}

【注意事项】
{holiday_notes}

【紧急联系方式】
如遇紧急情况，请联系：
{emergency_contact}

祝大家节日快乐！

{company_name}
{date}''',
        'variables': [
            {'name': 'holiday_name', 'label': '节假日名称', 'required': True},
            {'name': 'holiday_period', 'label': '放假时间', 'required': True},
            {'name': 'holiday_notes', 'label': '注意事项', 'required': False},
            {'name': 'emergency_contact', 'label': '紧急联系方式', 'required': False},
            {'name': 'company_name', 'label': '公司名称', 'required': True},
            {'name': 'date', 'label': '公告日期', 'required': True}
        ]
    },
    {
        'id': 'activity_announcement',
        'name': '活动发布公告',
        'type': 'ACTIVITY',
        'template': '''活动发布公告

亲爱的用户：

我们很高兴地为您呈现一场精彩的活动！

【活动名称】
{activity_name}

【活动时间】
{activity_time}

【活动地点】
{activity_location}

【活动内容】
{activity_content}

【报名方式】
{signup_method}

【活动亮点】
{highlights}

参加本活动无需额外费用，欢迎所有感兴趣的用户踊跃报名！

如有任何疑问，请联系：
{contact_info}

期待与您相见！

{company_name}
{date}''',
        'variables': [
            {'name': 'activity_name', 'label': '活动名称', 'required': True},
            {'name': 'activity_time', 'label': '活动时间', 'required': True},
            {'name': 'activity_location', 'label': '活动地点', 'required': True},
            {'name': 'activity_content', 'label': '活动内容', 'required': True},
            {'name': 'signup_method', 'label': '报名方式', 'required': False},
            {'name': 'highlights', 'label': '活动亮点', 'required': False},
            {'name': 'contact_info', 'label': '联系方式', 'required': False},
            {'name': 'company_name', 'label': '公司名称', 'required': True},
            {'name': 'date', 'label': '公告日期', 'required': True}
        ]
    }
]


@bp_notice_category.route('/types', methods=['GET'])
@token_required
def get_notice_types(current_user):
    """获取公告类型列表 - 需要登录验证"""
    try:
        logger.info(f"【公告类型查询】用户: {current_user.account}")

        # 检查用户类型
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        # 根据用户类型过滤可见的公告类型
        if is_admin:
            visible_types = NOTICE_TYPES
        else:
            visible_types = {
                k: v for k, v in NOTICE_TYPES.items()
                if k in ['SYSTEM', 'GENERAL']
            }

        # 转换为列表格式
        type_list = []
        for type_code, type_info in visible_types.items():
            type_item = {
                'code': type_code,
                'name': type_info['name'],
                'description': type_info['description'],
                'color': type_info['color'],
                'icon': type_info['icon'],
                'priority': type_info['priority']
            }
            type_list.append(type_item)

        # 按优先级排序
        type_list.sort(key=lambda x: x['priority'])

        logger.info(f"【公告类型查询成功】用户: {current_user.account}, 类型数: {len(type_list)}")
        return jsonify({
            'success': True,
            'message': '公告类型查询成功',
            'data': {
                'types': type_list,
                'is_admin': is_admin
            }
        }), 200

    except Exception:
        logger.exception("【公告类型查询异常】")
        return jsonify({
            'success': False,
            'message': '查询失败',
            'data': None
        }), 500


@bp_notice_category.route('/types/<type_code>', methods=['GET'])
@token_required
def get_notice_type_detail(current_user, type_code):
    """获取指定公告类型详情 - 需要登录验证"""
    try:
        logger.info(f"【公告类型详情查询】用户: {current_user.account}, 类型: {type_code}")

        if type_code not in NOTICE_TYPES:
            return jsonify({
                'success': False,
                'message': '公告类型不存在',
                'data': None
            }), 404

        # 检查用户类型
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        type_info = NOTICE_TYPES[type_code]

        # 获取该类型公告的统计信息
        total_count = Notice.query.filter_by(notice_type=type_code).count()
        active_count = Notice.query.filter(
            and_(
                Notice.notice_type == type_code,
                Notice.status == 'APPROVED',
                or_(
                    Notice.expiration.is_(None),
                    Notice.expiration > datetime.utcnow()
                )
            )
        ).count()

        result = {
            'code': type_code,
            'name': type_info['name'],
            'description': type_info['description'],
            'color': type_info['color'],
            'icon': type_info['icon'],
            'priority': type_info['priority'],
            'target_users': type_info['target_users'],
            'statistics': {
                'total_count': total_count,
                'active_count': active_count
            }
        }

        logger.info(f"【公告类型详情查询成功】用户: {current_user.account}, 类型: {type_code}")
        return jsonify({
            'success': True,
            'message': '公告类型详情查询成功',
            'data': result
        }), 200

    except Exception:
        logger.exception("【公告类型详情查询异常】")
        return jsonify({
            'success': False,
            'message': '查询失败',
            'data': None
        }), 500


@bp_notice_category.route('/templates', methods=['GET'])
@token_required
@admin_required
def get_notice_templates(current_user):
    """获取公告模板列表 - 需要管理员权限"""
    try:
        logger.info(f"【公告模板查询】管理员: {current_user.account}")

        # 过滤模板，根据管理员权限显示
        templates = []
        for template in NOTICE_TEMPLATES:
            template_data = {
                'id': template['id'],
                'name': template['name'],
                'type': template['type'],
                'type_name': NOTICE_TYPES[template['type']]['name'],
                'variables': template['variables']
            }
            templates.append(template_data)

        logger.info(f"【公告模板查询成功】管理员: {current_user.account}, 模板数: {len(templates)}")
        return jsonify({
            'success': True,
            'message': '公告模板查询成功',
            'data': {
                'templates': templates
            }
        }), 200

    except Exception:
        logger.exception("【公告模板查询异常】")
        return jsonify({
            'success': False,
            'message': '查询失败',
            'data': None
        }), 500


@bp_notice_category.route('/templates/<template_id>', methods=['GET'])
@token_required
@admin_required
def get_notice_template_detail(current_user, template_id):
    """获取指定公告模板详情 - 需要管理员权限"""
    try:
        logger.info(f"【公告模板详情查询】管理员: {current_user.account}, 模板ID: {template_id}")

        # 查找模板
        template = next((t for t in NOTICE_TEMPLATES if t['id'] == template_id), None)
        if not template:
            return jsonify({
                'success': False,
                'message': '模板不存在',
                'data': None
            }), 404

        result = {
            'id': template['id'],
            'name': template['name'],
            'type': template['type'],
            'template': template['template'],
            'variables': template['variables']
        }

        logger.info(f"【公告模板详情查询成功】管理员: {current_user.account}, 模板: {template['name']}")
        return jsonify({
            'success': True,
            'message': '模板详情查询成功',
            'data': result
        }), 200

    except Exception:
        logger.exception("【公告模板详情查询异常】")
        return jsonify({
            'success': False,
            'message': '查询失败',
            'data': None
        }), 500


@bp_notice_category.route('/templates/apply', methods=['POST'])
@token_required
@admin_required
def apply_notice_template(current_user):
    """应用公告模板生成公告内容 - 需要管理员权限"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据不能为空',
                'data': None
            }), 400

        template_id = data.get('template_id')
        variables = data.get('variables', {})

        if not template_id:
            return jsonify({
                'success': False,
                'message': '模板ID不能为空',
                'data': None
            }), 400

        logger.info(f"【应用公告模板】管理员: {current_user.account}, 模板ID: {template_id}")

        # 查找模板
        template = next((t for t in NOTICE_TEMPLATES if t['id'] == template_id), None)
        if not template:
            return jsonify({
                'success': False,
                'message': '模板不存在',
                'data': None
            }), 404

        # 验证必填变量
        required_vars = [v['name'] for v in template['variables'] if v.get('required', False)]
        missing_vars = [var for var in required_vars if var not in variables or not variables[var]]
        if missing_vars:
            return jsonify({
                'success': False,
                'message': f'缺少必填变量：{", ".join(missing_vars)}',
                'data': None
            }), 400

        # 应用模板
        try:
            content = template['template'].format(**variables)
        except KeyError as e:
            return jsonify({
                'success': False,
                'message': f'模板变量缺失：{str(e)}',
                'data': None
            }), 400

        result = {
            'template_id': template_id,
            'template_name': template['name'],
            'notice_type': template['type'],
            'title': variables.get('title', template['name']),
            'content': content,
            'applied_variables': variables
        }

        logger.info(f"【应用公告模板成功】管理员: {current_user.account}, 模板: {template['name']}")
        return jsonify({
            'success': True,
            'message': '模板应用成功',
            'data': result
        }), 200

    except Exception:
        logger.exception("【应用公告模板异常】")
        return jsonify({
            'success': False,
            'message': '应用失败',
            'data': None
        }), 500


@bp_notice_category.route('/push-rules', methods=['GET'])
@token_required
@admin_required
def get_push_rules(current_user):
    """获取公告推送规则配置 - 需要管理员权限"""
    try:
        logger.info(f"【推送规则查询】管理员: {current_user.account}")

        push_rules = {
            'SYSTEM': {
                'target_users': ['ALL'],
                'push_channels': ['web', 'email', 'sms'],
                'priority': 'high',
                'immediate': True,
                'description': '系统通知立即推送给所有用户'
            },
            'ACTIVITY': {
                'target_users': ['USER'],
                'push_channels': ['web', 'email'],
                'priority': 'medium',
                'immediate': False,
                'description': '活动公告推送给普通用户并可通过邮件或站内消息提醒'
            },
            'GENERAL': {
                'target_users': ['USER'],
                'push_channels': ['web'],
                'priority': 'low',
                'immediate': False,
                'description': '其他公告按计划推送给普通用户'
            }
        }

        user_types = [
            {'value': 'ALL', 'label': '所有用户'},
            {'value': 'ADMIN', 'label': '管理员'},
            {'value': 'USER', 'label': '普通用户'}
        ]

        push_channels = [
            {'value': 'web', 'label': '站内消息'},
            {'value': 'email', 'label': '邮件通知'},
            {'value': 'sms', 'label': '短信通知'}
        ]

        result = {
            'push_rules': push_rules,
            'user_types': user_types,
            'push_channels': push_channels
        }

        logger.info(f"【推送规则查询成功】管理员: {current_user.account}")
        return jsonify({
            'success': True,
            'message': '推送规则查询成功',
            'data': result
        }), 200

    except Exception:
        logger.exception("【推送规则查询异常】")
        return jsonify({
            'success': False,
            'message': '查询失败',
            'data': None
        }), 500


@bp_notice_category.route('/validate', methods=['POST'])
@token_required
@admin_required
def validate_notice_config(current_user):
    """验证公告配置的有效性 - 需要管理员权限"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据不能为空',
                'data': None
            }), 400

        notice_type = data.get('notice_type', '').strip()
        target_user_type = data.get('target_user_type', '').strip()
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        expiration = data.get('expiration', '').strip()

        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }

        # 验证公告类型
        if notice_type not in NOTICE_TYPES:
            validation_result['is_valid'] = False
            validation_result['errors'].append('无效的公告类型')
        else:
            # 验证推送范围
            if not NoticePermissionUtils.validate_notice_access_scope(notice_type, target_user_type):
                validation_result['is_valid'] = False
                validation_result['errors'].append('公告类型与推送范围不匹配')

        # 验证标题
        if not title:
            validation_result['is_valid'] = False
            validation_result['errors'].append('公告标题不能为空')
        elif len(title) > 150:
            validation_result['is_valid'] = False
            validation_result['errors'].append('公告标题不能超过150个字符')

        # 验证内容
        if not content:
            validation_result['is_valid'] = False
            validation_result['errors'].append('公告内容不能为空')
        elif len(content) > 10000:
            validation_result['warnings'].append('公告内容较长，建议控制在10000字符以内')

        # 验证到期时间
        if expiration:
            try:
                expiration_date = datetime.fromisoformat(expiration.replace('Z', '+00:00'))
                # 转为 UTC naive
                if expiration_date.tzinfo:
                    expiration_date = expiration_date.replace(tzinfo=None)
                if expiration_date <= datetime.utcnow():
                    validation_result['is_valid'] = False
                    validation_result['errors'].append('到期时间不能早于当前时间')
                elif expiration_date > datetime.utcnow() + timedelta(days=365):
                    validation_result['warnings'].append('到期时间过远，建议设置在一年内')
            except ValueError:
                validation_result['is_valid'] = False
                validation_result['errors'].append('到期时间格式无效')
        else:
            validation_result['warnings'].append('建议设置公告到期时间')

        logger.info(f"【公告配置验证】管理员: {current_user.account}, 验证结果: {validation_result['is_valid']}")

        return jsonify({
            'success': True,
            'message': '配置验证完成',
            'data': validation_result
        }), 200

    except Exception:
        logger.exception("【公告配置验证异常】")
        return jsonify({
            'success': False,
            'message': '验证失败',
            'data': None
        }), 500


# ------------------------------------------------------------------------------
# 4.2 bp_notice_public - 公开访问接口 (原 notice/public.py)
# ------------------------------------------------------------------------------

bp_notice_public = Blueprint('notice_public', __name__, url_prefix='/api/public/notice')


@bp_notice_public.route('/list', methods=['GET'])
def get_public_notices():
    """获取公开发布的公告列表（无需登录）"""
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        notice_type = request.args.get('notice_type', '').strip()
        release_time_start = request.args.get('release_time_start', '').strip()
        release_time_end = request.args.get('release_time_end', '').strip()
        release_title = request.args.get('title', '').strip()

        # 构建查询
        query = Notice.query.filter_by(status='APPROVED')

        # 类型筛选
        if notice_type:
            query = query.filter(Notice.notice_type == notice_type)

        # 标题搜索
        if release_title:
            query = query.filter(Notice.release_title.like(f'%{release_title}%'))

        # 发布时间范围筛选
        def parse_time(time_str):
            if not time_str:
                return None
            try:
                if time_str.endswith('Z'):
                    time_str = time_str.replace('Z', '+00:00')
                return datetime.fromisoformat(time_str)
            except ValueError:
                return None

        start_time = parse_time(release_time_start)
        if start_time:
            query = query.filter(Notice.release_time >= start_time)

        end_time = parse_time(release_time_end)
        if end_time:
            query = query.filter(Notice.release_time <= end_time)

        # 检查过期状态（不显示已过期的公告）
        current_time = datetime.utcnow()
        query = query.filter(
            (Notice.expiration.is_(None)) | (Notice.expiration > current_time)
        )

        # 分页查询
        pagination = query.order_by(Notice.release_time.desc()).paginate(page=page, per_page=size)
        notices = pagination.items
        total = pagination.total

        result = []
        for notice in notices:
            # 处理附件字段
            attachments = []
            if notice.attachments:
                for attachment in notice.attachments:
                    attachments.append({
                        'id': attachment.id,
                        'file_name': attachment.file_name,
                        'file_path': attachment.file_path,
                        'file_size': attachment.file_size,
                        'file_type': attachment.file_type,
                        'upload_time': attachment.upload_time.isoformat() + 'Z' if attachment.upload_time else None,
                        'uploader_account': attachment.uploader_account
                    })

            result.append({
                'id': notice.id,
                'release_time': notice.release_time.isoformat() + 'Z',
                'update_time': notice.update_time.isoformat() + 'Z' if notice.update_time else None,
                'release_title': notice.release_title,
                'summary': notice.release_notice[:200] + '...' if len(notice.release_notice) > 200 else notice.release_notice,
                'notice_type': notice.notice_type,
                'expiration': notice.expiration.isoformat() + 'Z' if notice.expiration else None,
                'is_expired': notice.is_expired,
                'attachment_count': len(attachments),
                'attachments': attachments
            })

        return ResponseService.paginated_success(
            items=result,
            total=total,
            page=page,
            size=size,
            message="公告列表查询成功"
        )

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_notice_public.route('/detail/<int:notice_id>', methods=['GET'])
def get_public_notice_detail(notice_id):
    """获取公开发布的公告详情（无需登录）"""
    try:
        notice = Notice.query.filter_by(id=notice_id, status='APPROVED').first()
        if not notice:
            return ResponseService.error('公告不存在或未发布', status_code=404)

        # 检查过期状态
        notice.check_expiration()
        if notice.is_expired:
            return ResponseService.error('公告已过期', status_code=410)

        # 处理附件字段
        attachments = []
        if notice.attachments:
            for attachment in notice.attachments:
                attachments.append({
                    'id': attachment.id,
                    'file_name': attachment.file_name,
                    'file_path': attachment.file_path,
                    'file_size': attachment.file_size,
                    'file_type': attachment.file_type,
                    'upload_time': attachment.upload_time.isoformat() + 'Z' if attachment.upload_time else None,
                    'uploader_account': attachment.uploader_account
                })

        result = {
            'id': notice.id,
            'release_time': notice.release_time.isoformat() + 'Z',
            'update_time': notice.update_time.isoformat() + 'Z' if notice.update_time else None,
            'release_title': notice.release_title,
            'release_notice': notice.release_notice,
            'notice_type': notice.notice_type,
            'expiration': notice.expiration.isoformat() + 'Z' if notice.expiration else None,
            'is_expired': notice.is_expired,
            'author_display': notice.author_display,
            'attachments': attachments
        }

        return ResponseService.success(data=result, message="公告详情查询成功")

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_notice_public.route('/statistics', methods=['GET'])
def get_public_notice_statistics():
    """获取公告统计信息（无需登录）"""
    try:
        # UTC naive datetime
        current_time = datetime.utcnow()

        # 基本统计：已发布且未过期的公告
        total_active = Notice.query.filter_by(status='APPROVED').filter(
            (Notice.expiration.is_(None)) | (Notice.expiration > current_time)
        ).count()

        # 按类型统计
        type_stats = db.session.query(
            Notice.notice_type,
            func.count(Notice.id).label('count')
        ).filter_by(status='APPROVED').filter(
            (Notice.expiration.is_(None)) | (Notice.expiration > current_time)
        ).group_by(Notice.notice_type).all()

        type_distribution = {notice_type: count for notice_type, count in type_stats}

        # 最近发布的公告（最近30天）
        thirty_days_ago = current_time - timedelta(days=30)
        recent_count = Notice.query.filter(
            Notice.status == 'APPROVED',
            Notice.release_time >= thirty_days_ago
        ).filter(
            (Notice.expiration.is_(None)) | (Notice.expiration > current_time)
        ).count()

        # 过期公告数量
        expired_count = Notice.query.filter(
            Notice.status == 'APPROVED',
            Notice.expiration.isnot(None),
            Notice.expiration <= current_time
        ).count()

        statistics = {
            'total_active': total_active,
            'expired_count': expired_count,
            'recent_30days': recent_count,
            'type_distribution': type_distribution
        }

        return ResponseService.success(data=statistics, message="公告统计查询成功")

    except Exception as e:
        return ResponseService.error(f'统计查询失败：{str(e)}', status_code=500)


@bp_notice_public.route('/types', methods=['GET'])
def get_public_notice_types():
    """获取公告类型列表（无需登录）"""
    try:
        # 定义公告类型
        notice_types = [
            {'value': 'SYSTEM', 'label': '系统通知', 'description': '系统级别的重要通知'},
            {'value': 'ACTIVITY', 'label': '活动公告', 'description': '活动相关的公告信息'},
            {'value': 'GENERAL', 'label': '其他公告', 'description': '其他类型的公告信息'}
        ]

        return ResponseService.success(data=notice_types, message="公告类型查询成功")

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# ------------------------------------------------------------------------------
# 4.3 bp_notice_user - 用户端公告操作 (原 user/notice_ops.py)
# ------------------------------------------------------------------------------

bp_notice_user = Blueprint('notice_user', __name__, url_prefix='/api/notice')


@bp_notice_user.route('/list', methods=['GET'])
@token_required
def get_notice_list(current_user):
    """获取用户公告列表（置顶公告优先展示，支持分页和类型筛选）"""
    try:
        logger.info(f"【用户公告列表查询】用户: {current_user.account}")

        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        notice_type = request.args.get('type', '').strip() or None

        # 检查用户类型
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        # 获取公告列表
        result = NoticeUtils.get_user_notice_list(
            user_id=current_user.id,
            page=page,
            size=size,
            notice_type=notice_type,
            is_admin=is_admin
        )

        logger.info(f"【用户公告列表查询成功】用户: {current_user.account}, 总数: {result['total']}, 未读数: {result['unread_count']}")
        return jsonify({
            'success': True,
            'message': '公告列表查询成功',
            'data': result
        }), 200

    except Exception:
        logger.exception("【用户公告列表查询异常】")
        return jsonify({
            'success': False,
            'message': '查询失败',
            'data': None
        }), 500


@bp_notice_user.route('/detail/<int:notice_id>', methods=['GET'])
@token_required
def get_notice_detail(current_user, notice_id):
    """获取公告详情（查看时自动标记为已读）"""
    try:
        logger.info(f"【用户公告详情查询】用户: {current_user.account}, 公告ID: {notice_id}")

        # 检查用户类型
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        # 权限校验
        can_view, error_msg = NoticePermissionUtils.can_user_view_notice(
            user_id=current_user.id,
            notice_id=notice_id,
            is_admin=is_admin
        )

        if not can_view:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 403

        # 获取公告详情
        notice_detail = NoticeQueryUtils.get_notice_with_attachments(notice_id)
        if not notice_detail:
            return jsonify({
                'success': False,
                'message': '公告不存在',
                'data': None
            }), 404

        # 自动标记为已读
        NoticeUtils.mark_notice_as_read(current_user.id, notice_id)

        # 获取最新的未读数量
        unread_count = NoticeUtils.get_user_unread_count(current_user.id, is_admin)

        result_data = {
            **notice_detail,
            'unread_count': unread_count
        }

        logger.info(f"【用户公告详情查询成功】用户: {current_user.account}, 公告标题: {notice_detail['title']}")
        return jsonify({
            'success': True,
            'message': '公告详情查询成功',
            'data': result_data
        }), 200

    except Exception:
        logger.exception("【用户公告详情查询异常】")
        return jsonify({
            'success': False,
            'message': '查询失败',
            'data': None
        }), 500


@bp_notice_user.route('/read/<int:notice_id>', methods=['POST'])
@token_required
def mark_notice_as_read(current_user, notice_id):
    """手动标记公告为已读"""
    try:
        logger.info(f"【标记公告已读】用户: {current_user.account}, 公告ID: {notice_id}")

        # 检查用户类型
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        # 权限校验
        can_view, error_msg = NoticePermissionUtils.can_user_view_notice(
            user_id=current_user.id,
            notice_id=notice_id,
            is_admin=is_admin
        )

        if not can_view:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 403

        # 标记为已读
        success = NoticeUtils.mark_notice_as_read(current_user.id, notice_id)
        if not success:
            return jsonify({
                'success': False,
                'message': '标记失败，公告可能不存在或已失效',
                'data': None
            }), 400

        # 获取最新的未读数量
        unread_count = NoticeUtils.get_user_unread_count(current_user.id, is_admin)

        logger.info(f"【标记公告已读成功】用户: {current_user.account}, 公告ID: {notice_id}")
        return jsonify({
            'success': True,
            'message': '已成功标记为已读',
            'data': {
                'notice_id': notice_id,
                'unread_count': unread_count
            }
        }), 200

    except Exception:
        logger.exception("【标记公告已读异常】")
        return jsonify({
            'success': False,
            'message': '操作失败',
            'data': None
        }), 500


@bp_notice_user.route('/read/all', methods=['POST'])
@token_required
def mark_all_notices_as_read(current_user):
    """标记所有公告为已读"""
    try:
        logger.info(f"【标记全部公告已读】用户: {current_user.account}")

        # 检查用户类型
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        # 标记所有公告为已读
        read_count = NoticeUtils.mark_all_notices_as_read(
            user_id=current_user.id,
            is_admin=is_admin
        )

        # 获取最新的未读数量（应该为0）
        unread_count = NoticeUtils.get_user_unread_count(current_user.id, is_admin)

        logger.info(f"【标记全部公告已读成功】用户: {current_user.account}, 标记数量: {read_count}")
        return jsonify({
            'success': True,
            'message': f'已成功标记 {read_count} 条公告为已读',
            'data': {
                'marked_count': read_count,
                'unread_count': unread_count
            }
        }), 200

    except Exception:
        logger.exception("【标记全部公告已读异常】")
        return jsonify({
            'success': False,
            'message': '操作失败',
            'data': None
        }), 500


@bp_notice_user.route('/unread/count', methods=['GET'])
@token_required
def get_unread_count(current_user):
    """获取用户未读公告数量"""
    try:
        logger.info(f"【未读公告数量查询】用户: {current_user.account}")

        # 检查用户类型
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        # 获取未读数量
        unread_count = NoticeUtils.get_user_unread_count(current_user.id, is_admin)

        logger.info(f"【未读公告数量查询成功】用户: {current_user.account}, 未读数: {unread_count}")
        return jsonify({
            'success': True,
            'message': '未读公告数量查询成功',
            'data': {
                'unread_count': unread_count
            }
        }), 200

    except Exception:
        logger.exception("【未读公告数量查询异常】")
        return jsonify({
            'success': False,
            'message': '查询失败',
            'data': None
        }), 500


@bp_notice_user.route('/types', methods=['GET'])
@token_required
def get_user_notice_types(current_user):
    """获取可用的公告类型列表"""
    try:
        logger.info(f"【公告类型查询】用户: {current_user.account}")

        # 检查用户类型
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        # 根据用户类型返回可用的公告类型
        types = [
            {'value': 'SYSTEM', 'label': '系统通知'},
            {'value': 'ACTIVITY', 'label': '活动公告'},
            {'value': 'GENERAL', 'label': '其他公告'}
        ]

        logger.info(f"【公告类型查询成功】用户: {current_user.account}, 管理员: {is_admin}")
        return jsonify({
            'success': True,
            'message': '公告类型查询成功',
            'data': {
                'types': types,
                'is_admin': is_admin
            }
        }), 200

    except Exception:
        logger.exception("【公告类型查询异常】")
        return jsonify({
            'success': False,
            'message': '查询失败',
            'data': None
        }), 500


@bp_notice_user.route('/search', methods=['GET'])
@token_required
def search_notices(current_user):
    """搜索公告（按标题和内容搜索）"""
    try:
        logger.info(f"【公告搜索】用户: {current_user.account}")

        # 获取查询参数
        keyword = request.args.get('keyword', '').strip()
        if not keyword:
            return jsonify({
                'success': False,
                'message': '搜索关键词不能为空',
                'data': None
            }), 400

        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        notice_type = request.args.get('type', '').strip() or None

        # 检查用户类型
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        # 构建搜索查询
        search_query = Notice.query.filter(
            and_(
                Notice.status == 'APPROVED',
                or_(
                    Notice.expiration.is_(None),
                    Notice.expiration > datetime.utcnow()
                ),
                or_(
                    Notice.release_title.like(f"%{keyword}%"),
                    Notice.release_notice.like(f"%{keyword}%")
                )
            )
        )

        # 根据用户类型过滤公告类型
        if not is_admin:
            search_query = search_query.filter(
                Notice.notice_type.in_(['SYSTEM', 'ACTIVITY', 'GENERAL'])
            )

        # 按类型筛选
        if notice_type:
            search_query = search_query.filter(Notice.notice_type == notice_type)

        # 排序和分页
        search_query = search_query.order_by(
            Notice.is_top.desc(),
            Notice.release_time.desc()
        )

        pagination = search_query.paginate(page=page, per_page=size, error_out=False)
        notices = pagination.items
        total = pagination.total

        # 构建返回数据
        notice_list = []
        for notice in notices:
            # 检查是否已读
            is_read = db.session.query(NoticeRead).filter(
                and_(
                    NoticeRead.user_id == current_user.id,
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

        # 获取未读数量
        unread_count = NoticeUtils.get_user_unread_count(current_user.id, is_admin)

        result = {
            'total': total,
            'page': page,
            'size': size,
            'items': notice_list,
            'unread_count': unread_count,
            'keyword': keyword
        }

        logger.info(f"【公告搜索成功】用户: {current_user.account}, 关键词: {keyword}, 结果数: {total}")
        return jsonify({
            'success': True,
            'message': '公告搜索成功',
            'data': result
        }), 200

    except Exception:
        logger.exception("【公告搜索异常】")
        return jsonify({
            'success': False,
            'message': '搜索失败',
            'data': None
        }), 500


# ------------------------------------------------------------------------------
# 4.4 bp_notice_admin - 管理员公告管理 (原 admin/notice_manage.py)
# ------------------------------------------------------------------------------

bp_notice_admin = Blueprint('notice_admin', __name__, url_prefix='/api/notice/admin')


@bp_notice_admin.route('/create', methods=['POST'])
@token_required
@admin_required
def create_notice(current_user):
    """创建公告 - 需要管理员权限"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据不能为空',
                'data': None
            }), 400

        # 验证必填字段
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        notice_type = data.get('notice_type', '').strip()

        if not title:
            return jsonify({
                'success': False,
                'message': '公告标题不能为空',
                'data': None
            }), 400

        if not content:
            return jsonify({
                'success': False,
                'message': '公告内容不能为空',
                'data': None
            }), 400

        if notice_type not in ['SYSTEM', 'ACTIVITY', 'GENERAL']:
            return jsonify({
                'success': False,
                'message': '无效的公告类型',
                'data': None
            }), 400

        # 获取当前管理员信息
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        if not current_admin:
            return jsonify({
                'success': False,
                'message': '管理员信息不存在',
                'data': None
            }), 404

        # 解析到期时间
        expiration = None
        if data.get('expiration'):
            try:
                expiration = datetime.fromisoformat(data['expiration'].replace('Z', '+00:00'))
                # 转为 UTC naive
                if expiration.tzinfo:
                    expiration = expiration.replace(tzinfo=None)
                if expiration <= datetime.utcnow():
                    return jsonify({
                        'success': False,
                        'message': '到期时间不能早于当前时间',
                        'data': None
                    }), 400
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': '到期时间格式无效',
                    'data': None
                }), 400

        # 创建公告
        notice = Notice(
            release_title=title,
            release_notice=content,
            notice_type=notice_type,
            expiration=expiration,
            author_user_id=current_admin.id,
            author_display=f"{current_admin.username}（管理员）",
            status='APPROVED'
        )

        # 如果模型支持置顶功能
        if hasattr(notice, 'is_top'):
            notice.is_top = data.get('is_top', False)

        db.session.add(notice)
        db.session.flush()

        # 处理附件（如果提供）
        attachments_data = data.get('attachments', [])
        if attachments_data:
            for attachment_data in attachments_data:
                if not all(key in attachment_data for key in ['file_name', 'file_path', 'file_size', 'file_type']):
                    continue

                attachment = NoticeAttachment(
                    notice_id=notice.id,
                    uploader_account=current_admin.account,
                    file_name=attachment_data['file_name'],
                    file_path=attachment_data['file_path'],
                    file_size=attachment_data['file_size'],
                    file_type=attachment_data['file_type']
                )
                db.session.add(attachment)

        db.session.commit()

        logger.info(f"【管理员创建公告成功】管理员: {current_user.account}, 公告ID: {notice.id}, 类型: {notice_type}")

        return jsonify({
            'success': True,
            'message': '公告创建成功',
            'data': {
                'id': notice.id,
                'title': notice.release_title,
                'notice_type': notice.notice_type,
                'status': notice.status,
                'release_time': notice.release_time.isoformat().replace('+00:00', 'Z'),
                'expiration': notice.expiration.isoformat().replace('+00:00', 'Z') if notice.expiration else None
            }
        }), 200

    except Exception:
        db.session.rollback()
        logger.exception("【管理员创建公告异常】")
        return jsonify({
            'success': False,
            'message': '创建失败',
            'data': None
        }), 500


@bp_notice_admin.route('/update/<int:notice_id>', methods=['PUT'])
@token_required
@admin_required
def update_notice(current_user, notice_id):
    """更新公告 - 需要管理员权限"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据不能为空',
                'data': None
            }), 400

        # 获取公告
        notice = Notice.query.get(notice_id)
        if not notice:
            return jsonify({
                'success': False,
                'message': '公告不存在',
                'data': None
            }), 404

        # 获取当前管理员信息
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        if not current_admin:
            return jsonify({
                'success': False,
                'message': '管理员信息不存在',
                'data': None
            }), 404

        # 权限校验
        can_manage, error_msg = NoticePermissionUtils.can_admin_manage_notice(
            admin_user_id=current_admin.id,
            notice=notice
        )

        if not can_manage:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 403

        # 更新字段
        update_fields = []

        if 'title' in data:
            title = data['title'].strip()
            if not title:
                return jsonify({
                    'success': False,
                    'message': '公告标题不能为空',
                    'data': None
                }), 400
            notice.release_title = title
            update_fields.append('title')

        if 'content' in data:
            content = data['content'].strip()
            if not content:
                return jsonify({
                    'success': False,
                    'message': '公告内容不能为空',
                    'data': None
                }), 400
            notice.release_notice = content
            update_fields.append('content')

        if 'notice_type' in data:
            notice_type = data['notice_type'].strip()
            if notice_type not in ['SYSTEM', 'ACTIVITY', 'GENERAL']:
                return jsonify({
                    'success': False,
                    'message': '无效的公告类型',
                    'data': None
                }), 400
            notice.notice_type = notice_type
            update_fields.append('notice_type')

        if 'expiration' in data:
            if data['expiration']:
                try:
                    expiration = datetime.fromisoformat(data['expiration'].replace('Z', '+00:00'))
                    # 转为 UTC naive
                    if expiration.tzinfo:
                        expiration = expiration.replace(tzinfo=None)
                    if expiration <= datetime.utcnow():
                        return jsonify({
                            'success': False,
                            'message': '到期时间不能早于当前时间',
                            'data': None
                        }), 400
                    notice.expiration = expiration
                except ValueError:
                    return jsonify({
                        'success': False,
                        'message': '到期时间格式无效',
                        'data': None
                    }), 400
            else:
                notice.expiration = None
            update_fields.append('expiration')

        if hasattr(notice, 'is_top') and 'is_top' in data:
            notice.is_top = data['is_top']
            update_fields.append('is_top')

        # 更新修改时间
        notice.update_time = datetime.utcnow()

        db.session.commit()

        logger.info(f"【管理员更新公告成功】管理员: {current_user.account}, 公告ID: {notice_id}, 更新字段: {update_fields}")

        return jsonify({
            'success': True,
            'message': '公告更新成功',
            'data': {
                'id': notice.id,
                'updated_fields': update_fields,
                'update_time': notice.update_time.isoformat().replace('+00:00', 'Z')
            }
        }), 200

    except Exception:
        db.session.rollback()
        logger.exception("【管理员更新公告异常】")
        return jsonify({
            'success': False,
            'message': '更新失败',
            'data': None
        }), 500


@bp_notice_admin.route('/delete/<int:notice_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_notice(current_user, notice_id):
    """删除公告（软删除，状态改为REJECTED） - 需要管理员权限"""
    try:
        # 获取公告
        notice = Notice.query.get(notice_id)
        if not notice:
            return jsonify({
                'success': False,
                'message': '公告不存在',
                'data': None
            }), 404

        # 获取当前管理员信息
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        if not current_admin:
            return jsonify({
                'success': False,
                'message': '管理员信息不存在',
                'data': None
            }), 404

        # 权限校验
        can_manage, error_msg = NoticePermissionUtils.can_admin_manage_notice(
            admin_user_id=current_admin.id,
            notice=notice
        )

        if not can_manage:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 403

        # 软删除：状态改为REJECTED
        notice.status = 'REJECTED'
        notice.update_time = datetime.utcnow()

        db.session.commit()

        logger.info(f"【管理员删除公告成功】管理员: {current_user.account}, 公告ID: {notice_id}")

        return jsonify({
            'success': True,
            'message': '公告删除成功',
            'data': {
                'id': notice.id,
                'status': notice.status
            }
        }), 200

    except Exception:
        db.session.rollback()
        logger.exception("【管理员删除公告异常】")
        return jsonify({
            'success': False,
            'message': '删除失败',
            'data': None
        }), 500


@bp_notice_admin.route('/list', methods=['GET'])
@token_required
@admin_required
def get_admin_notice_list(current_user):
    """管理员获取公告列表（支持条件筛选） - 需要管理员权限"""
    try:
        logger.info(f"【管理员公告列表查询】管理员: {current_user.account}")

        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status_filter = request.args.get('status', '').strip() or None
        type_filter = request.args.get('type', '').strip() or None
        date_from = request.args.get('date_from', '').strip() or None
        date_to = request.args.get('date_to', '').strip() or None
        author_filter = request.args.get('author', '').strip() or None

        # 构建基础查询
        base_query = Notice.query

        # 应用筛选条件
        filtered_query = NoticeQueryUtils.build_admin_filter_query(
            base_query=base_query,
            status_filter=status_filter,
            type_filter=type_filter,
            date_from=date_from,
            date_to=date_to,
            author_filter=author_filter
        )

        # 排序：置顶优先，然后按发布时间倒序
        if hasattr(Notice, 'is_top'):
            filtered_query = filtered_query.order_by(
                Notice.is_top.desc(),
                Notice.release_time.desc()
            )
        else:
            filtered_query = filtered_query.order_by(Notice.release_time.desc())

        # 分页查询
        pagination = filtered_query.paginate(page=page, per_page=size, error_out=False)
        notices = pagination.items
        total = pagination.total

        # 构建返回数据
        notice_list = []
        for notice in notices:
            # 获取已读统计
            read_stats = NoticeUtils.get_notice_read_statistics(notice.id)

            notice_data = {
                'id': notice.id,
                'title': notice.release_title,
                'content': notice.release_notice[:100] + '...' if len(notice.release_notice) > 100 else notice.release_notice,
                'notice_type': notice.notice_type,
                'status': notice.status,
                'is_top': getattr(notice, 'is_top', False),
                'is_expired': notice.is_expired,
                'release_time': notice.release_time.isoformat().replace('+00:00', 'Z'),
                'update_time': notice.update_time.isoformat().replace('+00:00', 'Z'),
                'expiration': notice.expiration.isoformat().replace('+00:00', 'Z') if notice.expiration else None,
                'author_display': notice.author_display,
                'author_user_id': notice.author_user_id,
                'attachment_count': len(notice.attachments) if notice.attachments else 0,
                'read_stats': read_stats
            }
            notice_list.append(notice_data)

        result = {
            'total': total,
            'page': page,
            'size': size,
            'items': notice_list,
            'filters': {
                'status': status_filter,
                'type': type_filter,
                'date_from': date_from,
                'date_to': date_to,
                'author': author_filter
            }
        }

        logger.info(f"【管理员公告列表查询成功】管理员: {current_user.account}, 总数: {total}")
        return jsonify({
            'success': True,
            'message': '公告列表查询成功',
            'data': result
        }), 200

    except Exception:
        logger.exception("【管理员公告列表查询异常】")
        return jsonify({
            'success': False,
            'message': '查询失败',
            'data': None
        }), 500


@bp_notice_admin.route('/detail/<int:notice_id>', methods=['GET'])
@token_required
@admin_required
def get_admin_notice_detail(current_user, notice_id):
    """管理员获取公告详情（包含完整统计信息） - 需要管理员权限"""
    try:
        logger.info(f"【管理员公告详情查询】管理员: {current_user.account}, 公告ID: {notice_id}")

        # 获取公告详情
        notice_detail = NoticeQueryUtils.get_notice_with_attachments(notice_id)
        if not notice_detail:
            return jsonify({
                'success': False,
                'message': '公告不存在',
                'data': None
            }), 404

        # 获取已读统计
        read_stats = NoticeUtils.get_notice_read_statistics(notice_id)

        # 获取当前管理员信息
        current_admin = Admin.query.filter_by(account=current_user.account).first()

        # 检查权限
        can_edit = False
        if current_admin and notice_detail['author_user_id'] == current_admin.id:
            can_edit = True

        result_data = {
            **notice_detail,
            'read_stats': read_stats,
            'can_edit': can_edit
        }

        logger.info(f"【管理员公告详情查询成功】管理员: {current_user.account}, 公告标题: {notice_detail['title']}")
        return jsonify({
            'success': True,
            'message': '公告详情查询成功',
            'data': result_data
        }), 200

    except Exception:
        logger.exception("【管理员公告详情查询异常】")
        return jsonify({
            'success': False,
            'message': '查询失败',
            'data': None
        }), 500


@bp_notice_admin.route('/top/<int:notice_id>', methods=['POST'])
@token_required
@admin_required
def toggle_notice_top(current_user, notice_id):
    """切换公告置顶状态 - 需要管理员权限"""
    try:
        data = request.get_json()
        if not data or 'is_top' not in data:
            return jsonify({
                'success': False,
                'message': '缺少置顶状态参数',
                'data': None
            }), 400

        # 获取公告
        notice = Notice.query.get(notice_id)
        if not notice:
            return jsonify({
                'success': False,
                'message': '公告不存在',
                'data': None
            }), 404

        # 检查模型是否支持置顶功能
        if not hasattr(notice, 'is_top'):
            return jsonify({
                'success': False,
                'message': '当前公告模型不支持置顶功能',
                'data': None
            }), 400

        # 获取当前管理员信息
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        if not current_admin:
            return jsonify({
                'success': False,
                'message': '管理员信息不存在',
                'data': None
            }), 404

        # 权限校验
        can_manage, error_msg = NoticePermissionUtils.can_admin_manage_notice(
            admin_user_id=current_admin.id,
            notice=notice
        )

        if not can_manage:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 403

        # 更新置顶状态
        old_top_status = notice.is_top
        notice.is_top = data['is_top']
        notice.update_time = datetime.utcnow()

        db.session.commit()

        action = "置顶" if notice.is_top else "取消置顶"
        logger.info(f"【管理员{action}公告成功】管理员: {current_user.account}, 公告ID: {notice_id}")

        return jsonify({
            'success': True,
            'message': f'公告{action}成功',
            'data': {
                'id': notice.id,
                'is_top': notice.is_top,
                'old_is_top': old_top_status,
                'update_time': notice.update_time.isoformat().replace('+00:00', 'Z')
            }
        }), 200

    except Exception:
        db.session.rollback()
        logger.exception("【管理员置顶公告异常】")
        return jsonify({
            'success': False,
            'message': '操作失败',
            'data': None
        }), 500


@bp_notice_admin.route('/statistics', methods=['GET'])
@token_required
@admin_required
def get_notice_statistics(current_user):
    """获取公告统计数据 - 需要管理员权限"""
    try:
        logger.info(f"【管理员公告统计查询】管理员: {current_user.account}")

        # 统计各状态公告数量
        status_stats = db.session.query(
            Notice.status,
            func.count(Notice.id)
        ).group_by(Notice.status).all()

        # 统计各类型公告数量
        type_stats = db.session.query(
            Notice.notice_type,
            func.count(Notice.id)
        ).group_by(Notice.notice_type).all()

        # 统计总公告数和活跃公告数
        total_count = Notice.query.count()
        active_count = Notice.query.filter(
            and_(
                Notice.status == 'APPROVED',
                or_(
                    Notice.expiration.is_(None),
                    Notice.expiration > datetime.utcnow()
                )
            )
        ).count()

        # 统计置顶公告数量（如果支持）
        top_count = 0
        if hasattr(Notice, 'is_top'):
            top_count = Notice.query.filter(
                and_(
                    Notice.is_top == True,
                    Notice.status == 'APPROVED',
                    or_(
                        Notice.expiration.is_(None),
                        Notice.expiration > datetime.utcnow()
                    )
                )
            ).count()

        # 统计过期公告数量
        expired_count = Notice.query.filter(
            and_(
                Notice.expiration.isnot(None),
                Notice.expiration <= datetime.utcnow(),
                Notice.status != 'EXPIRED'
            )
        ).count()

        # 近期发布的公告数量（最近7天）
        recent_date = datetime.utcnow() - timedelta(days=7)
        recent_count = Notice.query.filter(
            Notice.release_time >= recent_date
        ).count()

        result = {
            'overview': {
                'total_count': total_count,
                'active_count': active_count,
                'top_count': top_count,
                'expired_count': expired_count,
                'recent_count': recent_count
            },
            'status_distribution': {status: count for status, count in status_stats},
            'type_distribution': {notice_type: count for notice_type, count in type_stats}
        }

        logger.info(f"【管理员公告统计查询成功】管理员: {current_user.account}")
        return jsonify({
            'success': True,
            'message': '公告统计数据查询成功',
            'data': result
        }), 200

    except Exception:
        logger.exception("【管理员公告统计查询异常】")
        return jsonify({
            'success': False,
            'message': '查询失败',
            'data': None
        }), 500


# ==============================================================================
# 5. 导出所有 Blueprint
# ==============================================================================

__all__ = [
    'bp_notice_category',
    'bp_notice_public',
    'bp_notice_user',
    'bp_notice_admin',
    'NoticeUtils',
    'NoticePermissionUtils',
    'NoticeQueryUtils'
]
