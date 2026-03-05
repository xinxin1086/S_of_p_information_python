# API_activities 模块 - 统一路由文件
# 本文件整合了所有活动相关的路由和工具类
# 原始文件结构:
#   - root.py (根路由 - 活动创建)
#   - common/utils.py (工具类)
#   - user/user_ops.py (用户操作)
#   - admin/activity_manage.py (管理员管理)
#   - booking/booking.py (预约接口)
#   - discussion/discuss.py (讨论评论)
#   - public/activity.py (公开访问)

# ==============================================================================
# 1. 导入语句
# ==============================================================================

from flask import Blueprint, request
from components import db, token_required
from components.models import (
    Activity, ActivityBooking, ActivityRating,
    ActivityDiscuss, ActivityDiscussComment, User
)
from components.response_service import ResponseService
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from sqlalchemy import text, func


# ==============================================================================
# 2. 工具类 (原 common/utils.py)
# ==============================================================================

class ActivityValidator:
    """活动相关验证工具类"""

    @staticmethod
    def is_activity_bookable(activity: Activity) -> tuple[bool, str]:
        """
        验证活动是否可预约

        Args:
            activity: 活动对象

        Returns:
            tuple[bool, str]: (是否可预约, 错误信息)
        """
        if not activity:
            return False, "活动不存在"

        # 检查活动状态
        if activity.status not in ['published']:
            return False, f"当前活动状态({activity.status})不允许预约"

        # 检查活动是否已结束
        if activity.end_time and activity.end_time < datetime.now():
            return False, "活动已结束，无法预约"

        # 检查活动是否已取消
        if activity.status == 'cancelled':
            return False, "活动已取消，无法预约"

        # 检查人数限制
        if activity.max_participants:
            current_booked = ActivityBooking.query.filter_by(
                activity_id=activity.id,
                status='booked'
            ).count()

            if current_booked >= activity.max_participants:
                return False, "活动预约人数已满"

        return True, ""

    @staticmethod
    def check_user_booking_conflict(user_account: str, activity_id: int) -> tuple[bool, Optional[ActivityBooking]]:
        """
        检查用户预约冲突

        Args:
            user_account: 用户账号
            activity_id: 活动ID

        Returns:
            tuple[bool, Optional[ActivityBooking]]: (是否有冲突, 现有预约记录)
        """
        existing_booking = ActivityBooking.query.filter_by(
            activity_id=activity_id,
            user_account=user_account
        ).first()

        if existing_booking and existing_booking.status == 'booked':
            return True, existing_booking

        return False, existing_booking

    @staticmethod
    def can_user_rate_activity(user_id: int, activity_id: int) -> tuple[bool, str]:
        """
        验证用户是否可以为活动评分

        Args:
            user_id: 用户ID
            activity_id: 活动ID

        Returns:
            tuple[bool, str]: (是否可评分, 错误信息)
        """
        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return False, "活动不存在"

        # 检查用户是否已参与活动
        user_participated = ActivityBooking.query.filter_by(
            activity_id=activity_id,
            user_id=user_id,
            status='attended'
        ).first()

        if not user_participated:
            return False, "您需要参与活动后才能评分"

        # 检查是否已经评分过
        existing_rating = ActivityRating.query.filter_by(
            activity_id=activity_id,
            rater_user_id=user_id
        ).first()

        if existing_rating:
            return False, "您已经为该活动评过分"

        return True, ""

    @staticmethod
    def is_activity_manageable(activity: Activity, user_id: int) -> tuple[bool, str]:
        """
        验证用户是否可以管理活动

        Args:
            activity: 活动对象
            user_id: 用户ID

        Returns:
            tuple[bool, str]: (是否可管理, 错误信息)
        """
        if not activity:
            return False, "活动不存在"

        if activity.organizer_user_id != user_id:
            return False, "无权限管理此活动"

        return True, ""


class ActivityStatistics:
    """活动统计工具类"""

    @staticmethod
    def get_booking_statistics(activity_id: int) -> Dict[str, Any]:
        """
        获取活动预约统计信息

        Args:
            activity_id: 活动ID

        Returns:
            Dict: 统计信息
        """
        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            raise ValueError("活动不存在")

        # 预约统计
        stats = db.session.execute(text("""
            SELECT
                COUNT(*) as total_bookings,
                SUM(CASE WHEN status = 'booked' THEN 1 ELSE 0 END) as booked_count,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_count,
                SUM(CASE WHEN status = 'attended' THEN 1 ELSE 0 END) as attended_count,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent_count
            FROM activity_bookings
            WHERE activity_id = :activity_id
        """), {"activity_id": activity_id}).fetchone()

        return {
            'activity_id': activity_id,
            'max_participants': activity.max_participants,
            'total_bookings': stats.total_bookings or 0,
            'current_booked': stats.booked_count or 0,
            'cancelled_bookings': stats.cancelled_count or 0,
            'attended_bookings': stats.attended_count or 0,
            'absent_bookings': stats.absent_count or 0,
            'available_spots': max(0, activity.max_participants - (stats.booked_count or 0)) if activity.max_participants else None,
            'attendance_rate': round((stats.attended_count or 0) / (stats.total_bookings or 1) * 100, 2)
        }

    @staticmethod
    def get_rating_statistics(activity_id: int) -> Dict[str, Any]:
        """
        获取活动评分统计信息

        Args:
            activity_id: 活动ID

        Returns:
            Dict: 评分统计信息
        """
        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            raise ValueError("活动不存在")

        # 评分统计
        stats = db.session.execute(text("""
            SELECT
                COUNT(*) as total_ratings,
                AVG(score) as average_score,
                MIN(score) as min_score,
                MAX(score) as max_score,
                SUM(CASE WHEN score = 5 THEN 1 ELSE 0 END) as five_star_count,
                SUM(CASE WHEN score = 4 THEN 1 ELSE 0 END) as four_star_count,
                SUM(CASE WHEN score = 3 THEN 1 ELSE 0 END) as three_star_count,
                SUM(CASE WHEN score = 2 THEN 1 ELSE 0 END) as two_star_count,
                SUM(CASE WHEN score = 1 THEN 1 ELSE 0 END) as one_star_count
            FROM activity_rating
            WHERE activity_id = :activity_id
        """), {"activity_id": activity_id}).fetchone()

        total_ratings = stats.total_ratings or 0
        rating_distribution = {
            '5_star': stats.five_star_count or 0,
            '4_star': stats.four_star_count or 0,
            '3_star': stats.three_star_count or 0,
            '2_star': stats.two_star_count or 0,
            '1_star': stats.one_star_count or 0
        }

        return {
            'activity_id': activity_id,
            'total_ratings': total_ratings,
            'average_score': round(float(stats.average_score), 2) if stats.average_score else 0,
            'min_score': stats.min_score or 0,
            'max_score': stats.max_score or 0,
            'rating_distribution': rating_distribution,
            'rating_percentage': {
                '5_star': round((rating_distribution['5_star'] / max(1, total_ratings)) * 100, 1),
                '4_star': round((rating_distribution['4_star'] / max(1, total_ratings)) * 100, 1),
                '3_star': round((rating_distribution['3_star'] / max(1, total_ratings)) * 100, 1),
                '2_star': round((rating_distribution['2_star'] / max(1, total_ratings)) * 100, 1),
                '1_star': round((rating_distribution['1_star'] / max(1, total_ratings)) * 100, 1)
            }
        }


class ActivityStatusManager:
    """活动状态管理工具类"""

    @staticmethod
    def update_activity_status(activity: Activity, new_status: str, user_id: int = None) -> tuple[bool, str]:
        """
        更新活动状态

        Args:
            activity: 活动对象
            new_status: 新状态
            user_id: 操作用户ID

        Returns:
            tuple[bool, str]: (是否成功, 错误信息)
        """
        valid_statuses = ['draft', 'published', 'cancelled', 'completed']

        if new_status not in valid_statuses:
            return False, f"无效的活动状态，支持的值: {', '.join(valid_statuses)}"

        # 状态流转验证
        old_status = activity.status
        status_transitions = {
            'draft': ['published', 'cancelled'],
            'published': ['cancelled', 'completed'],
            'cancelled': [],  # 取消状态不可逆
            'completed': []   # 完成状态不可逆
        }

        if new_status not in status_transitions.get(old_status, []):
            return False, f"无法从状态 '{old_status}' 转换到 '{new_status}'"

        # 特殊验证
        if new_status == 'completed':
            # 检查活动是否已结束
            if activity.end_time and activity.end_time > datetime.now():
                return False, "活动尚未结束，无法标记为完成"

        # 更新状态
        activity.status = new_status
        activity.updated_at = datetime.now()

        return True, f"活动状态已从 '{old_status}' 更新为 '{new_status}'"

    @staticmethod
    def get_status_flow_info() -> Dict[str, list]:
        """
        获取状态流转信息

        Returns:
            Dict: 状态流转映射
        """
        return {
            'draft': {
                'description': '草稿状态',
                'next_statuses': ['published', 'cancelled'],
                'can_book': False,
                'can_rate': False
            },
            'published': {
                'description': '已发布状态',
                'next_statuses': ['cancelled', 'completed'],
                'can_book': True,
                'can_rate': False
            },
            'cancelled': {
                'description': '已取消状态',
                'next_statuses': [],
                'can_book': False,
                'can_rate': False
            },
            'completed': {
                'description': '已完成状态',
                'next_statuses': [],
                'can_book': False,
                'can_rate': True
            }
        }


class ActivitySearchHelper:
    """活动搜索辅助工具类"""

    @staticmethod
    def build_activity_query(filters: Dict[str, Any]) -> Any:
        """
        构建活动查询对象

        Args:
            filters: 筛选条件

        Returns:
            Query: SQLAlchemy查询对象
        """
        query = Activity.query

        # 状态筛选
        if 'status' in filters and filters['status']:
            query = query.filter(Activity.status == filters['status'])

        # 发布者筛选
        if 'organizer_user_id' in filters and filters['organizer_user_id']:
            query = query.filter(Activity.organizer_user_id == filters['organizer_user_id'])

        # 关键词搜索
        if 'keyword' in filters and filters['keyword']:
            keyword = f"%{filters['keyword']}%"
            query = query.filter(
                (Activity.title.like(keyword)) |
                (Activity.description.like(keyword)) |
                (Activity.location.like(keyword))
            )

        # 标签筛选
        if 'tags' in filters and filters['tags']:
            for tag in filters['tags']:
                query = query.filter(Activity.tags.contains([tag]))

        # 时间范围筛选
        if 'start_time_from' in filters and filters['start_time_from']:
            query = query.filter(Activity.start_time >= filters['start_time_from'])

        if 'start_time_to' in filters and filters['start_time_to']:
            query = query.filter(Activity.start_time <= filters['start_time_to'])

        if 'end_time_from' in filters and filters['end_time_from']:
            query = query.filter(Activity.end_time >= filters['end_time_from'])

        if 'end_time_to' in filters and filters['end_time_to']:
            query = query.filter(Activity.end_time <= filters['end_time_to'])

        return query


# ==============================================================================
# 3. 蓝图创建和路由注册
# ==============================================================================

# ------------------------------------------------------------------------------
# 3.1 root_bp - 根路由 (原 root.py)
# ------------------------------------------------------------------------------

root_bp = Blueprint('api_activities_root', __name__, url_prefix='/api/activities')


@root_bp.route('', methods=['POST'])
@root_bp.route('/', methods=['POST'])
@token_required
def create_activity_public(current_user):
    """
    前端创建活动兼容接口：POST /api/activities
    允许已登录用户创建活动（组织者为当前用户）
    """
    try:
        # 先打印原始请求体，以诊断JSON问题
        raw_data = request.get_data(as_text=True)
        print(f"【原始请求体】{repr(raw_data)}")

        data = request.get_json(force=True, silent=False)
        print(f"【创建活动请求】用户: {current_user.account}, 请求数据: {data}")
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        location = data.get('location', '').strip()
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        max_participants = data.get('max_participants')
        tags = data.get('tags', [])
        status = data.get('status', 'draft')
        print(f"【解析参数】title={title}, start_time={start_time}, end_time={end_time}, max_participants={max_participants}")

        # 权限检查：仅允许组织用户或管理员创建
        role = (getattr(current_user, 'role', '') or '').upper()
        print(f"【权限检查】用户角色: {role}")
        if role not in ('ORG_USER', 'ADMIN', 'SUPER_ADMIN'):
            return ResponseService.error('仅组织者或管理员可以创建活动', status_code=403)
        print(f"【权限验证通过】")

        # 验证必填字段
        if not title:
            return ResponseService.error('活动标题不能为空', status_code=400)
        if not start_time or not end_time:
            return ResponseService.error('活动时间不能为空', status_code=400)
        if max_participants is None:
            return ResponseService.error('最大参与人数不能为空', status_code=400)

        print(f"【必填字段验证通过】")
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        print(f"【时间解析成功】start_dt={start_dt}, end_dt={end_dt}")
        if start_dt >= end_dt:
            return ResponseService.error('活动开始时间必须早于结束时间', status_code=400)

        # 使用 UTC 时间进行比较（避免 naive vs aware datetime 冲突）
        now_utc = datetime.now(timezone.utc)
        if start_dt < now_utc:
            print(f"【时间验证失败】start_dt={start_dt} < now_utc={now_utc}")
            return ResponseService.error('活动开始时间不能早于当前时间', status_code=400)

        valid_statuses = ['draft', 'published']
        if status not in valid_statuses:
            return ResponseService.error(f'无效的活动状态，支持的值: {", ".join(valid_statuses)}', status_code=400)

        print(f"【活动数据验证通过】")
        activity = Activity(
            title=title,
            description=description,
            location=location,
            start_time=start_dt,
            end_time=end_dt,
            max_participants=int(max_participants) if max_participants else None,
            organizer_user_id=current_user.id,
            organizer_display=current_user.username,
            tags=tags if tags else [],
            status=status
        )

        db.session.add(activity)
        db.session.commit()
        print(f"【活动创建成功】活动ID: {activity.id}")

        activity_data = {
            'id': activity.id,
            'title': activity.title,
            'description': activity.description,
            'location': activity.location,
            'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'max_participants': activity.max_participants,
            'current_participants': 0,
            'tags': activity.tags or [],
            'status': activity.status,
            'organizer_display': activity.organizer_display,
            'created_at': activity.created_at.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=activity_data, message='活动创建成功')

    except Exception as e:
        print(f"【活动创建异常】错误类型: {type(e).__name__}, 错误信息: {str(e)}")
        import traceback
        print(f"【错误堆栈】{traceback.format_exc()}")
        db.session.rollback()
        return ResponseService.error(f'活动创建失败: {str(e)}', status_code=500)


# ------------------------------------------------------------------------------
# 3.2 user_ops_bp - 用户操作路由 (原 user/user_ops.py)
# ------------------------------------------------------------------------------

user_ops_bp = Blueprint('user_ops', __name__, url_prefix='/api/activities/user')


@user_ops_bp.route('/activities/<int:activity_id>/booking', methods=['POST'])
@token_required
def book_activity(current_user, activity_id):
    """用户预约活动"""
    try:
        print(f"【用户预约活动请求】用户: {current_user.account}, 活动ID: {activity_id}")

        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 验证活动是否可预约
        can_book, error_msg = ActivityValidator.is_activity_bookable(activity)
        if not can_book:
            return ResponseService.error(error_msg, status_code=400)

        # 检查用户预约冲突
        has_conflict, existing_booking = ActivityValidator.check_user_booking_conflict(
            current_user.account, activity_id
        )

        if has_conflict:
            return ResponseService.error('您已经预约过该活动', status_code=400)

        # 如果有取消过的预约记录，重新激活
        if existing_booking and existing_booking.status == 'cancelled':
            existing_booking.status = 'booked'
            existing_booking.notes = None
            existing_booking.updated_at = datetime.now()
            db.session.commit()

            print(f"【预约重新激活】预约ID: {existing_booking.id}, 用户: {current_user.account}")

            booking_data = {
                'id': existing_booking.id,
                'activity_id': existing_booking.activity_id,
                'user_account': existing_booking.user_account,
                'status': existing_booking.status,
                'booking_time': existing_booking.booking_time.isoformat().replace('+00:00', 'Z')
            }

            return ResponseService.success(data=booking_data, message='活动预约成功')

        # 创建新预约
        data = request.get_json() or {}
        booking = ActivityBooking(
            activity_id=activity_id,
            user_account=current_user.account,
            status='booked',
            notes=data.get('notes', '')
        )

        db.session.add(booking)
        db.session.commit()

        print(f"【预约创建成功】预约ID: {booking.id}, 用户: {current_user.account}")

        booking_data = {
            'id': booking.id,
            'activity_id': booking.activity_id,
            'user_account': booking.user_account,
            'status': booking.status,
            'notes': booking.notes,
            'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=booking_data, message='活动预约成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'预约失败: {str(e)}', status_code=500)


@user_ops_bp.route('/activities/<int:activity_id>/booking', methods=['DELETE'])
@token_required
def cancel_booking(current_user, activity_id):
    """用户取消预约"""
    try:
        print(f"【用户取消预约请求】用户: {current_user.account}, 活动ID: {activity_id}")

        # 查找用户的预约记录
        booking = ActivityBooking.query.filter_by(
            activity_id=activity_id,
            user_account=current_user.account,
            status='booked'
        ).first()

        if not booking:
            return ResponseService.error('未找到有效的预约记录', status_code=404)

        # 验证活动是否允许取消预约
        activity = Activity.query.get(activity_id)
        if activity and activity.status == 'completed':
            return ResponseService.error('活动已结束，无法取消预约', status_code=400)

        # 更新预约状态为取消
        booking.status = 'cancelled'
        booking.updated_at = datetime.now()
        db.session.commit()

        print(f"【预约取消成功】预约ID: {booking.id}, 用户: {current_user.account}")

        return ResponseService.success(
            data={'id': booking.id, 'activity_id': activity_id},
            message='预约取消成功'
        )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'取消预约失败: {str(e)}', status_code=500)


@user_ops_bp.route('/bookings', methods=['GET'])
@token_required
def get_my_bookings(current_user):
    """获取用户的预约列表"""
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', '').strip()
        activity_status = request.args.get('activity_status', '').strip()

        # 构建查询
        query = ActivityBooking.query.filter_by(user_account=current_user.account)

        # 预约状态筛选
        if status:
            query = query.filter(ActivityBooking.status == status)

        # 按预约时间倒序排列
        query = query.order_by(ActivityBooking.booking_time.desc())

        # 分页查询
        pagination = query.paginate(page=page, per_page=size)
        bookings = pagination.items

        bookings_data = []
        for booking in bookings:
            # 获取活动信息
            activity = Activity.query.get(booking.activity_id)

            # 活动状态筛选
            if activity_status and activity and activity.status != activity_status:
                continue

            booking_info = {
                'id': booking.id,
                'activity_id': booking.activity_id,
                'activity_title': activity.title if activity else '活动已删除',
                'activity_description': activity.description if activity else None,
                'activity_location': activity.location if activity else None,
                'activity_start_time': activity.start_time.isoformat().replace('+00:00', 'Z') if activity else None,
                'activity_end_time': activity.end_time.isoformat().replace('+00:00', 'Z') if activity else None,
                'activity_max_participants': activity.max_participants if activity else None,
                'activity_current_participants': ActivityBooking.query.filter_by(
                    activity_id=booking.activity_id, status='booked'
                ).count(),
                'activity_organizer_display': activity.organizer_display if activity else None,
                'activity_tags': activity.tags if activity else [],
                'activity_status': activity.status if activity else None,
                'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z'),
                'status': booking.status,
                'notes': booking.notes
            }
            bookings_data.append(booking_info)

        # 手动分页（考虑状态筛选）
        total = len(bookings_data)
        start = (page - 1) * size
        end = start + size
        paginated_data = bookings_data[start:end]

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'items': paginated_data
        }, message='预约列表获取成功')

    except Exception as e:
        return ResponseService.error(f'获取预约列表失败: {str(e)}', status_code=500)


@user_ops_bp.route('/activities/<int:activity_id>/rating', methods=['POST'])
@token_required
def create_activity_rating(current_user, activity_id):
    """用户为活动评分"""
    try:
        print(f"【用户活动评分请求】用户: {current_user.account}, 活动ID: {activity_id}")

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        score = data.get('score')
        comment = data.get('comment', '')

        # 验证评分
        if not score or not (1 <= int(score) <= 5):
            return ResponseService.error('评分必须是1-5的整数', status_code=400)

        # 验证用户是否可以评分
        can_rate, error_msg = ActivityValidator.can_user_rate_activity(current_user.id, activity_id)
        if not can_rate:
            return ResponseService.error(error_msg, status_code=400)

        # 创建评分
        rating = ActivityRating(
            activity_id=activity_id,
            score=int(score),
            comment_content=comment.strip() if comment else None
        )
        # 设置评分者信息
        rating.set_rater_info(current_user)

        db.session.add(rating)
        db.session.commit()

        print(f"【评分创建成功】评分ID: {rating.id}, 用户: {current_user.account}")

        rating_data = {
            'id': rating.id,
            'activity_id': rating.activity_id,
            'rater_user_id': rating.rater_user_id,
            'rater_display': rating.rater_display,
            'rater_avatar': rating.rater_avatar,
            'score': rating.score,
            'comment_content': rating.comment_content,
            'create_time': rating.create_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=rating_data, message='评分发表成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'评分发表失败: {str(e)}', status_code=500)


@user_ops_bp.route('/activities/<int:activity_id>/rating', methods=['PUT'])
@token_required
def update_activity_rating(current_user, activity_id):
    """用户更新活动评分"""
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        # 查找现有评分
        rating = ActivityRating.query.filter_by(
            activity_id=activity_id,
            rater_user_id=current_user.id
        ).first()

        if not rating:
            return ResponseService.error('您还未为该活动评分', status_code=404)

        # 更新评分和评语
        if 'score' in data:
            new_score = data['score']
            if not (1 <= int(new_score) <= 5):
                return ResponseService.error('评分必须是1-5的整数', status_code=400)
            rating.score = int(new_score)

        if 'comment_content' in data:
            rating.comment_content = data['comment_content'].strip() if data['comment_content'] else None

        rating.update_time = datetime.now()
        db.session.commit()

        print(f"【评分更新成功】评分ID: {rating.id}, 用户: {current_user.account}")

        rating_data = {
            'id': rating.id,
            'activity_id': rating.activity_id,
            'rater_display': rating.rater_display,
            'rater_avatar': rating.rater_avatar,
            'score': rating.score,
            'comment_content': rating.comment_content,
            'create_time': rating.create_time.isoformat().replace('+00:00', 'Z'),
            'update_time': rating.update_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=rating_data, message='评分更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'评分更新失败: {str(e)}', status_code=500)


@user_ops_bp.route('/activities/<int:activity_id>/rating', methods=['DELETE'])
@token_required
def delete_activity_rating(current_user, activity_id):
    """用户删除活动评分"""
    try:
        # 查找现有评分
        rating = ActivityRating.query.filter_by(
            activity_id=activity_id,
            rater_user_id=current_user.id
        ).first()

        if not rating:
            return ResponseService.error('您还未为该活动评分', status_code=404)

        db.session.delete(rating)
        db.session.commit()

        print(f"【评分删除成功】评分ID: {rating.id}, 用户: {current_user.account}")

        return ResponseService.success(
            data={'rating_id': rating.id},
            message='评分删除成功'
        )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'评分删除失败: {str(e)}', status_code=500)


@user_ops_bp.route('/ratings', methods=['GET'])
@token_required
def get_my_ratings(current_user):
    """获取用户的评分列表"""
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        activity_status = request.args.get('activity_status', '').strip()

        # 构建查询
        query = ActivityRating.query.filter_by(rater_user_id=current_user.id)
        query = query.order_by(ActivityRating.create_time.desc())

        # 分页查询
        pagination = query.paginate(page=page, per_page=size)
        ratings = pagination.items

        ratings_list = []
        for rating in ratings:
            # 获取活动信息
            activity = Activity.query.get(rating.activity_id)

            # 活动状态筛选
            if activity_status and activity and activity.status != activity_status:
                continue

            item = {
                'id': rating.id,
                'activity_id': rating.activity_id,
                'activity_title': activity.title if activity else '活动已删除',
                'activity_description': activity.description if activity else None,
                'activity_start_time': activity.start_time.isoformat().replace('+00:00', 'Z') if activity else None,
                'activity_end_time': activity.end_time.isoformat().replace('+00:00', 'Z') if activity else None,
                'activity_organizer_display': activity.organizer_display if activity else None,
                'activity_status': activity.status if activity else None,
                'score': rating.score,
                'comment_content': rating.comment_content,
                'create_time': rating.create_time.isoformat().replace('+00:00', 'Z'),
                'update_time': rating.update_time.isoformat().replace('+00:00', 'Z')
            }
            ratings_list.append(item)

        # 手动分页（考虑状态筛选）
        total = len(ratings_list)
        start = (page - 1) * size
        end = start + size
        paginated_data = ratings_list[start:end]

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'items': paginated_data
        }, message='评分列表获取成功')

    except Exception as e:
        return ResponseService.error(f'获取评分列表失败: {str(e)}', status_code=500)


@user_ops_bp.route('/activities/<int:activity_id>/discussions', methods=['POST'])
@token_required
def create_activity_discussion(current_user, activity_id):
    """用户创建活动讨论"""
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        content = data.get('content', '').strip()
        image_urls = data.get('image_urls', [])

        if not content:
            return ResponseService.error('讨论内容不能为空', status_code=400)

        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 创建讨论
        discussion = ActivityDiscuss(
            activity_id=activity_id,
            content=content,
            image_urls=image_urls if image_urls else None
        )
        # 设置发布者信息
        discussion.set_author_info(current_user)

        db.session.add(discussion)
        db.session.commit()

        print(f"【讨论创建成功】讨论ID: {discussion.id}, 用户: {current_user.account}")

        discussion_data = {
            'id': discussion.id,
            'activity_id': discussion.activity_id,
            'content': discussion.content,
            'author_user_id': discussion.author_user_id,
            'author_display': discussion.author_display,
            'author_avatar': discussion.author_avatar,
            'image_urls': discussion.image_urls or [],
            'create_time': discussion.create_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=discussion_data, message='讨论发表成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'讨论发表失败: {str(e)}', status_code=500)


@user_ops_bp.route('/discussions/<int:discussion_id>', methods=['PUT'])
@token_required
def update_activity_discussion(current_user, discussion_id):
    """用户更新活动讨论"""
    try:
        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        # 检查权限（只有作者可以修改）
        if discussion.author_user_id != current_user.id:
            return ResponseService.error('无权限修改此讨论', status_code=403)

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        # 更新内容
        if 'content' in data:
            new_content = data['content'].strip()
            if not new_content:
                return ResponseService.error('讨论内容不能为空', status_code=400)
            discussion.content = new_content

        if 'image_urls' in data:
            discussion.image_urls = data['image_urls']

        discussion.update_time = datetime.now()
        db.session.commit()

        print(f"【讨论更新成功】讨论ID: {discussion_id}, 用户: {current_user.account}")

        discussion_data = {
            'id': discussion.id,
            'activity_id': discussion.activity_id,
            'content': discussion.content,
            'author_display': discussion.author_display,
            'image_urls': discussion.image_urls or [],
            'create_time': discussion.create_time.isoformat().replace('+00:00', 'Z'),
            'update_time': discussion.update_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=discussion_data, message='讨论更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'讨论更新失败: {str(e)}', status_code=500)


@user_ops_bp.route('/discussions/<int:discussion_id>', methods=['DELETE'])
@token_required
def delete_activity_discussion(current_user, discussion_id):
    """用户删除活动讨论"""
    try:
        print(f"【删除讨论请求】讨论ID: {discussion_id}, 用户: {current_user.account}")

        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        # 验证是否为讨论作者
        if discussion.author_user_id != current_user.id:
            return ResponseService.error('无权删除此讨论', status_code=403)

        # 统计即将删除的留言数量
        comment_count = ActivityDiscussComment.query.filter_by(discuss_id=discussion_id).count()

        # 删除讨论（级联删除所有相关留言）
        db.session.delete(discussion)
        db.session.commit()

        print(f"【讨论删除成功】讨论ID: {discussion_id}, 用户: {current_user.account}")
        print(f"【级联删除留言】共删除 {comment_count} 条相关留言")

        return ResponseService.success(
            data={
                'id': discussion_id,
                'deleted_comment_count': comment_count
            },
            message='讨论删除成功，所有相关留言已删除'
        )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'讨论删除失败: {str(e)}', status_code=500)


@user_ops_bp.route('/my-activities', methods=['GET'])
@token_required
def get_my_activities(current_user):
    """获取用户参与的或创建的活动列表"""
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        role = request.args.get('role', 'all')  # organizer/participant/all
        status = request.args.get('status', '').strip()

        result_list = []

        if role in ['organizer', 'all']:
            # 获取用户创建的活动
            organizer_query = Activity.query.filter_by(organizer_user_id=current_user.id)
            if status:
                organizer_query = organizer_query.filter(Activity.status == status)

            organizer_activities = organizer_query.order_by(Activity.updated_at.desc()).all()

            for activity in organizer_activities:
                # 统计预约人数
                current_bookings = ActivityBooking.query.filter_by(
                    activity_id=activity.id, status='booked'
                ).count()

                item = {
                    'id': activity.id,
                    'title': activity.title,
                    'description': activity.description,
                    'location': activity.location,
                    'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
                    'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
                    'max_participants': activity.max_participants,
                    'current_participants': current_bookings,
                    'tags': activity.tags,
                    'status': activity.status,
                    'role': 'organizer',
                    'created_at': activity.created_at.isoformat().replace('+00:00', 'Z'),
                    'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z')
                }
                result_list.append(item)

        if role in ['participant', 'all']:
            # 获取用户参与的活动
            participant_query = ActivityBooking.query.filter_by(user_account=current_user.account)
            if status:
                # 需要关联活动表进行状态筛选
                participant_query = participant_query.join(Activity).filter(Activity.status == status)

            participant_bookings = participant_query.order_by(ActivityBooking.booking_time.desc()).all()

            for booking in participant_bookings:
                activity = Activity.query.get(booking.activity_id)
                if not activity:
                    continue

                # 避免重复添加（如果用户既是创建者也是参与者）
                if any(item['id'] == activity.id for item in result_list):
                    continue

                # 统计预约人数
                current_bookings = ActivityBooking.query.filter_by(
                    activity_id=activity.id, status='booked'
                ).count()

                item = {
                    'id': activity.id,
                    'title': activity.title,
                    'description': activity.description,
                    'location': activity.location,
                    'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
                    'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
                    'max_participants': activity.max_participants,
                    'current_participants': current_bookings,
                    'tags': activity.tags,
                    'status': activity.status,
                    'role': 'participant',
                    'booking_status': booking.status,
                    'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z'),
                    'created_at': activity.created_at.isoformat().replace('+00:00', 'Z'),
                    'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z')
                }
                result_list.append(item)

        # 按更新时间排序
        result_list.sort(key=lambda x: x['updated_at'], reverse=True)

        # 手动分页
        total = len(result_list)
        start = (page - 1) * size
        end = start + size
        paginated_data = result_list[start:end]

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'items': paginated_data
        }, message='我的活动列表查询成功')

    except Exception as e:
        return ResponseService.error(f'查询失败: {str(e)}', status_code=500)


# ------------------------------------------------------------------------------
# 3.3 admin_manage_bp - 管理员路由 (原 admin/activity_manage.py)
# ------------------------------------------------------------------------------

admin_manage_bp = Blueprint('admin_manage', __name__, url_prefix='/api/activities/admin')


@admin_manage_bp.route('/activities', methods=['POST'])
@token_required
def create_activity(current_user):
    """管理员创建活动"""
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        location = data.get('location', '').strip()
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        max_participants = data.get('max_participants')
        tags = data.get('tags', [])
        status = data.get('status', 'draft')

        # 验证必填字段
        if not title:
            return ResponseService.error('活动标题不能为空', status_code=400)
        if not start_time or not end_time:
            return ResponseService.error('活动时间不能为空', status_code=400)
        if not max_participants:
            return ResponseService.error('最大参与人数不能为空', status_code=400)

        # 验证时间逻辑
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        if start_dt >= end_dt:
            return ResponseService.error('活动开始时间必须早于结束时间', status_code=400)

        if start_dt < datetime.now(timezone.utc):
            return ResponseService.error('活动开始时间不能早于当前时间', status_code=400)

        # 验证状态
        valid_statuses = ['draft', 'published']
        if status not in valid_statuses:
            return ResponseService.error(f'无效的活动状态，支持的值: {", ".join(valid_statuses)}', status_code=400)

        # 创建活动
        activity = Activity(
            title=title,
            description=description,
            location=location,
            start_time=start_dt,
            end_time=end_dt,
            max_participants=int(max_participants),
            organizer_user_id=current_user.id,
            organizer_display=current_user.username,
            tags=tags if tags else [],
            status=status
        )

        db.session.add(activity)
        db.session.commit()

        print(f"【管理员创建活动】活动ID: {activity.id}, 用户: {current_user.account}")

        activity_data = {
            'id': activity.id,
            'title': activity.title,
            'description': activity.description,
            'location': activity.location,
            'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'max_participants': activity.max_participants,
            'current_participants': 0,
            'tags': activity.tags or [],
            'status': activity.status,
            'organizer_display': activity.organizer_display,
            'created_at': activity.created_at.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=activity_data, message='活动创建成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'活动创建失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/<int:activity_id>', methods=['PUT'])
@token_required
def update_activity(current_user, activity_id):
    """管理员更新活动"""
    try:
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 检查权限
        can_manage, error_msg = ActivityValidator.is_activity_manageable(activity, current_user.id)
        if not can_manage:
            return ResponseService.error(error_msg, status_code=403)

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        # 更新字段
        if 'title' in data:
            title = data['title'].strip()
            if not title:
                return ResponseService.error('活动标题不能为空', status_code=400)
            activity.title = title

        if 'description' in data:
            activity.description = data['description'].strip()

        if 'location' in data:
            activity.location = data['location'].strip()

        if 'start_time' in data:
            start_time = data['start_time']
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))

            # 如果有结束时间，验证时间逻辑
            if activity.end_time and start_dt >= activity.end_time:
                return ResponseService.error('活动开始时间必须早于结束时间', status_code=400)

            activity.start_time = start_dt

        if 'end_time' in data:
            end_time = data['end_time']
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))

            # 验证时间逻辑
            if activity.start_time and activity.start_time >= end_dt:
                return ResponseService.error('活动结束时间必须晚于开始时间', status_code=400)

            activity.end_time = end_dt

        if 'max_participants' in data:
            max_participants = data['max_participants']
            if not max_participants or int(max_participants) <= 0:
                return ResponseService.error('最大参与人数必须大于0', status_code=400)

            # 检查当前预约人数是否超过新的限制
            current_booked = ActivityBooking.query.filter_by(
                activity_id=activity_id,
                status='booked'
            ).count()

            if int(max_participants) < current_booked:
                return ResponseService.error(
                    f'当前已有{current_booked}人预约，不能将人数限制设置为{max_participants}',
                    status_code=400
                )

            activity.max_participants = int(max_participants)

        if 'tags' in data:
            activity.tags = data['tags']

        if 'status' in data:
            new_status = data['status'].strip()
            success, error_msg = ActivityStatusManager.update_activity_status(
                activity, new_status, current_user.id
            )
            if not success:
                return ResponseService.error(error_msg, status_code=400)

        activity.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        print(f"【管理员更新活动】活动ID: {activity_id}, 用户: {current_user.account}")

        # 获取当前参与人数
        current_bookings = ActivityBooking.query.filter_by(
            activity_id=activity_id,
            status='booked'
        ).count()

        activity_data = {
            'id': activity.id,
            'title': activity.title,
            'description': activity.description,
            'location': activity.location,
            'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'max_participants': activity.max_participants,
            'current_participants': current_bookings,
            'tags': activity.tags,
            'status': activity.status,
            'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=activity_data, message='活动更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'活动更新失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/<int:activity_id>', methods=['DELETE'])
@token_required
def delete_activity(current_user, activity_id):
    """管理员删除活动（软删除）"""
    try:
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 检查权限
        can_manage, error_msg = ActivityValidator.is_activity_manageable(activity, current_user.id)
        if not can_manage:
            return ResponseService.error(error_msg, status_code=403)

        # 检查是否有有效预约
        active_bookings = ActivityBooking.query.filter_by(
            activity_id=activity_id,
            status='booked'
        ).count()

        if active_bookings > 0:
            return ResponseService.error(
                f'活动有{active_bookings}个有效预约，无法删除。请先取消所有预约或将活动状态改为已取消。',
                status_code=400
            )

        # 软删除：更新状态为cancelled
        old_status = activity.status
        activity.status = 'cancelled'
        activity.updated_at = datetime.now()
        db.session.commit()

        print(f"【管理员删除活动】活动ID: {activity_id}, 用户: {current_user.account}, 状态: {old_status} -> cancelled")

        return ResponseService.success(message='活动删除成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'活动删除失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities', methods=['GET'])
@token_required
def get_activities(current_user):
    """管理员获取活动列表"""
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', '').strip()
        organizer_user_id = request.args.get('organizer_user_id', '').strip()
        keyword = request.args.get('keyword', '').strip()

        # 构建查询
        query = Activity.query

        # 状态筛选
        if status:
            query = query.filter(Activity.status == status)

        # 发布者筛选
        if organizer_user_id:
            query = query.filter(Activity.organizer_user_id == int(organizer_user_id))

        # 关键词搜索
        if keyword:
            keyword = f"%{keyword}%"
            query = query.filter(
                (Activity.title.like(keyword)) |
                (Activity.description.like(keyword)) |
                (Activity.location.like(keyword))
            )

        # 分页查询（按更新时间倒序）
        pagination = query.order_by(Activity.updated_at.desc()).paginate(page=page, per_page=size)
        activities = pagination.items
        total = pagination.total

        result_list = []
        for activity in activities:
            # 统计预约人数
            current_bookings = ActivityBooking.query.filter_by(
                activity_id=activity.id,
                status='booked'
            ).count()

            item = {
                'id': activity.id,
                'title': activity.title,
                'description': activity.description,
                'location': activity.location,
                'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
                'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
                'max_participants': activity.max_participants,
                'current_participants': current_bookings,
                'tags': activity.tags,
                'status': activity.status,
                'organizer_user_id': activity.organizer_user_id,
                'organizer_display': activity.organizer_display,
                'created_at': activity.created_at.isoformat().replace('+00:00', 'Z'),
                'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z')
            }
            result_list.append(item)

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'items': result_list
        }, message='活动列表查询成功')

    except Exception as e:
        return ResponseService.error(f'查询失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/<int:activity_id>', methods=['GET'])
@token_required
def get_activity_detail(current_user, activity_id):
    """管理员获取活动详情"""
    try:
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 检查权限（只有活动发布者可以查看详情）
        can_manage, error_msg = ActivityValidator.is_activity_manageable(activity, current_user.id)
        if not can_manage:
            return ResponseService.error(error_msg, status_code=403)

        # 获取预约统计
        booking_stats = ActivityStatistics.get_booking_statistics(activity_id)

        # 获取评分统计
        rating_stats = ActivityStatistics.get_rating_statistics(activity_id)

        activity_data = {
            'id': activity.id,
            'title': activity.title,
            'description': activity.description,
            'location': activity.location,
            'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'max_participants': activity.max_participants,
            'tags': activity.tags,
            'status': activity.status,
            'organizer_user_id': activity.organizer_user_id,
            'organizer_display': activity.organizer_display,
            'created_at': activity.created_at.isoformat().replace('+00:00', 'Z'),
            'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z'),
            'booking_statistics': booking_stats,
            'rating_statistics': rating_stats
        }

        return ResponseService.success(data=activity_data, message='活动详情查询成功')

    except Exception as e:
        return ResponseService.error(f'查询失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/<int:activity_id>/bookings', methods=['GET'])
@token_required
def get_activity_bookings_admin(current_user, activity_id):
    """管理员获取活动预约列表"""
    try:
        # 验证活动存在和权限
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        can_manage, error_msg = ActivityValidator.is_activity_manageable(activity, current_user.id)
        if not can_manage:
            return ResponseService.error(error_msg, status_code=403)

        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', '').strip()

        # 构建查询
        query = ActivityBooking.query.filter_by(activity_id=activity_id)

        # 状态筛选
        if status:
            query = query.filter(ActivityBooking.status == status)

        # 分页查询
        pagination = query.order_by(ActivityBooking.booking_time.desc()).paginate(page=page, per_page=size)
        bookings = pagination.items
        total = pagination.total

        bookings_data = []
        for booking in bookings:
            # 获取用户信息
            user = User.query.filter_by(account=booking.user_account, is_deleted=0).first()

            booking_info = {
                'id': booking.id,
                'activity_id': booking.activity_id,
                'user_account': booking.user_account,
                'user_display': user.username if user else '用户已注销',
                'user_avatar': user.avatar if user else None,
                'user_phone': user.phone if user else None,
                'user_email': user.email if user else None,
                'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z'),
                'status': booking.status,
                'notes': booking.notes,
                'updated_at': booking.updated_at.isoformat().replace('+00:00', 'Z') if booking.updated_at else None
            }
            bookings_data.append(booking_info)

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'items': bookings_data
        }, message='预约列表获取成功')

    except Exception as e:
        return ResponseService.error(f'获取预约列表失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/<int:activity_id>/bookings/<int:booking_id>/status', methods=['PUT'])
@token_required
def update_booking_status_admin(current_user, activity_id, booking_id):
    """管理员更新预约状态"""
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        new_status = data.get('status')
        notes = data.get('notes', '')

        if not new_status:
            return ResponseService.error('状态不能为空', status_code=400)

        # 验证状态值
        valid_statuses = ['booked', 'cancelled', 'attended', 'absent']
        if new_status not in valid_statuses:
            return ResponseService.error(f'无效的状态值，支持的值: {", ".join(valid_statuses)}', status_code=400)

        # 验证活动存在和权限
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        can_manage, error_msg = ActivityValidator.is_activity_manageable(activity, current_user.id)
        if not can_manage:
            return ResponseService.error(error_msg, status_code=403)

        # 查找预约记录
        booking = ActivityBooking.query.filter_by(
            id=booking_id,
            activity_id=activity_id
        ).first()

        if not booking:
            return ResponseService.error('预约记录不存在', status_code=404)

        old_status = booking.status
        booking.status = new_status
        booking.notes = notes
        booking.updated_at = datetime.now()
        db.session.commit()

        print(f"【管理员更新预约状态】预约ID: {booking_id}, 状态: {old_status} -> {new_status}, 操作者: {current_user.account}")

        return ResponseService.success({
            'booking_id': booking_id,
            'activity_id': activity_id,
            'old_status': old_status,
            'new_status': new_status,
            'notes': notes,
            'updated_time': booking.updated_at.isoformat().replace('+00:00', 'Z')
        }, message='预约状态更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'更新预约状态失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/<int:activity_id>/bookings/batch', methods=['POST'])
@token_required
def batch_update_bookings_admin(current_user, activity_id):
    """管理员批量操作预约"""
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        operation = data.get('operation')  # confirm_attendance/mark_absent/cancel
        booking_ids = data.get('booking_ids', [])

        if not operation:
            return ResponseService.error('操作类型不能为空', status_code=400)

        if not booking_ids:
            return ResponseService.error('预约ID列表不能为空', status_code=400)

        # 验证操作类型
        operation_map = {
            'confirm_attendance': 'attended',
            'mark_absent': 'absent',
            'cancel': 'cancelled'
        }

        if operation not in operation_map:
            return ResponseService.error(f'无效的操作类型，支持的值: {", ".join(operation_map.keys())}', status_code=400)

        # 验证活动存在和权限
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        can_manage, error_msg = ActivityValidator.is_activity_manageable(activity, current_user.id)
        if not can_manage:
            return ResponseService.error(error_msg, status_code=403)

        # 查询要操作的预约
        bookings = ActivityBooking.query.filter(
            ActivityBooking.id.in_(booking_ids),
            ActivityBooking.activity_id == activity_id
        ).all()

        if not bookings:
            return ResponseService.error('未找到可操作的预约记录', status_code=404)

        new_status = operation_map[operation]
        success_count = 0
        error_count = 0
        errors = []

        for booking in bookings:
            try:
                old_status = booking.status
                booking.status = new_status
                booking.updated_at = datetime.now()
                success_count += 1
                print(f"【批量操作预约】预约ID: {booking.id}, 状态: {old_status} -> {new_status}")

            except Exception as e:
                error_count += 1
                errors.append(f"预约ID {booking.id}: {str(e)}")

        if success_count > 0:
            db.session.commit()

        return ResponseService.success({
            'operation': operation,
            'activity_id': activity_id,
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors
        }, message=f'批量操作完成，成功: {success_count} 个，失败: {error_count} 个')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'批量操作失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/<int:activity_id>/statistics', methods=['GET'])
@token_required
def get_activity_statistics_admin(current_user, activity_id):
    """管理员获取活动统计信息"""
    try:
        # 验证活动存在和权限
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        can_manage, error_msg = ActivityValidator.is_activity_manageable(activity, current_user.id)
        if not can_manage:
            return ResponseService.error(error_msg, status_code=403)

        # 获取预约统计
        booking_stats = ActivityStatistics.get_booking_statistics(activity_id)

        # 获取评分统计
        rating_stats = ActivityStatistics.get_rating_statistics(activity_id)

        statistics = {
            'activity_id': activity_id,
            'activity_title': activity.title,
            'activity_status': activity.status,
            'booking_statistics': booking_stats,
            'rating_statistics': rating_stats,
            'updated_at': datetime.now().isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=statistics, message='活动统计查询成功')

    except Exception as e:
        return ResponseService.error(f'统计查询失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/summary', methods=['GET'])
@token_required
def get_activities_summary(current_user):
    """管理员获取活动汇总信息"""
    try:
        # 基础统计
        stats = db.session.execute(text("""
            SELECT
                COUNT(*) as total_activities,
                SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) as draft_count,
                SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published_count,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_count,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count
            FROM activities
            WHERE organizer_user_id = :user_id
        """), {"user_id": current_user.id}).fetchone()

        # 预约统计
        booking_stats = db.session.execute(text("""
            SELECT
                COUNT(*) as total_bookings,
                SUM(CASE WHEN status = 'booked' THEN 1 ELSE 0 END) as booked_count,
                SUM(CASE WHEN status = 'attended' THEN 1 ELSE 0 END) as attended_count,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_count
            FROM activity_bookings ab
            JOIN activities a ON ab.activity_id = a.id
            WHERE a.organizer_user_id = :user_id
        """), {"user_id": current_user.id}).fetchone()

        # 评分统计
        rating_stats = db.session.execute(text("""
            SELECT
                COUNT(*) as total_ratings,
                AVG(score) as average_score
            FROM activity_rating ar
            JOIN activities a ON ar.activity_id = a.id
            WHERE a.organizer_user_id = :user_id
        """), {"user_id": current_user.id}).fetchone()

        summary = {
            'user_id': current_user.id,
            'user_display': current_user.username,
            'activities': {
                'total': stats.total_activities or 0,
                'draft': stats.draft_count or 0,
                'published': stats.published_count or 0,
                'cancelled': stats.cancelled_count or 0,
                'completed': stats.completed_count or 0
            },
            'bookings': {
                'total': booking_stats.total_bookings or 0,
                'booked': booking_stats.booked_count or 0,
                'attended': booking_stats.attended_count or 0,
                'cancelled': booking_stats.cancelled_count or 0
            },
            'ratings': {
                'total': rating_stats.total_ratings or 0,
                'average_score': round(float(rating_stats.average_score), 2) if rating_stats.average_score else 0
            },
            'updated_at': datetime.now().isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=summary, message='活动汇总查询成功')

    except Exception as e:
        return ResponseService.error(f'汇总查询失败: {str(e)}', status_code=500)


# ------------------------------------------------------------------------------
# 3.4 booking_bp - 预约路由 (原 booking/booking.py)
# ------------------------------------------------------------------------------

booking_bp = Blueprint('booking', __name__, url_prefix='/api/activities/booking')


@booking_bp.route('/activities/<int:activity_id>/book', methods=['POST'])
@token_required
def create_booking(current_user, activity_id):
    """创建活动预约"""
    try:
        print(f"【预约接口调用】用户: {current_user.account}, 活动ID: {activity_id}")

        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 验证活动是否可预约
        can_book, error_msg = ActivityValidator.is_activity_bookable(activity)
        if not can_book:
            return ResponseService.error(error_msg, status_code=400)

        # 检查用户预约冲突
        has_conflict, existing_booking = ActivityValidator.check_user_booking_conflict(
            current_user.account, activity_id
        )

        if has_conflict:
            return ResponseService.error('您已经预约过该活动', status_code=400)

        # 如果有取消过的预约记录，重新激活
        if existing_booking and existing_booking.status == 'cancelled':
            existing_booking.status = 'booked'
            existing_booking.notes = None
            existing_booking.updated_at = datetime.now()
            db.session.commit()

            print(f"【预约重新激活】预约ID: {existing_booking.id}")

            booking_data = {
                'id': existing_booking.id,
                'activity_id': existing_booking.activity_id,
                'user_account': existing_booking.user_account,
                'status': existing_booking.status,
                'booking_time': existing_booking.booking_time.isoformat().replace('+00:00', 'Z')
            }

            return ResponseService.success(data=booking_data, message='预约成功')

        # 创建新预约
        data = request.get_json() or {}
        booking = ActivityBooking(
            activity_id=activity_id,
            user_account=current_user.account,
            status='booked',
            notes=data.get('notes', '')
        )

        db.session.add(booking)
        db.session.commit()

        print(f"【预约创建成功】预约ID: {booking.id}")

        booking_data = {
            'id': booking.id,
            'activity_id': booking.activity_id,
            'user_account': booking.user_account,
            'status': booking.status,
            'notes': booking.notes,
            'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=booking_data, message='预约成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'预约失败: {str(e)}', status_code=500)


@booking_bp.route('/activities/<int:activity_id>/cancel', methods=['DELETE'])
@token_required
def cancel_booking_route(current_user, activity_id):
    """取消活动预约"""
    try:
        print(f"【取消预约接口调用】用户: {current_user.account}, 活动ID: {activity_id}")

        # 查找用户的预约记录
        booking = ActivityBooking.query.filter_by(
            activity_id=activity_id,
            user_account=current_user.account,
            status='booked'
        ).first()

        if not booking:
            return ResponseService.error('未找到有效的预约记录', status_code=404)

        # 验证活动是否允许取消预约
        activity = Activity.query.get(activity_id)
        if activity and activity.status == 'completed':
            return ResponseService.error('活动已结束，无法取消预约', status_code=400)

        # 更新预约状态为取消
        booking.status = 'cancelled'
        booking.updated_at = datetime.now()
        db.session.commit()

        print(f"【预约取消成功】预约ID: {booking.id}")

        return ResponseService.success(
            data={'id': booking.id, 'activity_id': activity_id},
            message='预约取消成功'
        )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'取消预约失败: {str(e)}', status_code=500)


@booking_bp.route('/activities/<int:activity_id>/bookings', methods=['GET'])
@token_required
def get_activity_bookings(current_user, activity_id):
    """获取活动预约列表（管理员/组织者）"""
    try:
        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 检查权限（只有活动组织者可以查看预约列表）
        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限查看此活动的预约列表', status_code=403)

        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', '').strip()

        # 构建查询
        query = ActivityBooking.query.filter_by(activity_id=activity_id)

        # 状态筛选
        if status:
            query = query.filter(ActivityBooking.status == status)

        # 分页查询
        pagination = query.order_by(ActivityBooking.booking_time.desc()).paginate(page=page, per_page=size)
        bookings = pagination.items
        total = pagination.total

        bookings_data = []
        for booking in bookings:
            # 获取用户信息
            user = User.query.filter_by(account=booking.user_account, is_deleted=0).first()

            booking_info = {
                'id': booking.id,
                'activity_id': booking.activity_id,
                'user_account': booking.user_account,
                'user_display': user.username if user else '用户已注销',
                'user_avatar': user.avatar if user else None,
                'user_phone': user.phone if user else None,
                'user_email': user.email if user else None,
                'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z'),
                'status': booking.status,
                'notes': booking.notes,
                'updated_at': booking.updated_at.isoformat().replace('+00:00', 'Z') if booking.updated_at else None
            }
            bookings_data.append(booking_info)

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'items': bookings_data
        }, message='预约列表获取成功')

    except Exception as e:
        return ResponseService.error(f'获取预约列表失败: {str(e)}', status_code=500)


@booking_bp.route('/my-bookings', methods=['GET'])
@token_required
def get_user_bookings(current_user):
    """获取用户的预约列表"""
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', '').strip()
        activity_status = request.args.get('activity_status', '').strip()

        # 构建查询
        query = ActivityBooking.query.filter_by(user_account=current_user.account)

        # 预约状态筛选
        if status:
            query = query.filter(ActivityBooking.status == status)

        # 按预约时间倒序排列
        query = query.order_by(ActivityBooking.booking_time.desc())

        # 分页查询
        pagination = query.paginate(page=page, per_page=size)
        bookings = pagination.items
        total = pagination.total

        bookings_data = []
        for booking in bookings:
            # 获取活动信息
            activity = Activity.query.get(booking.activity_id)

            # 活动状态筛选
            if activity_status and activity and activity.status != activity_status:
                continue

            # 获取当前预约人数
            current_booked = ActivityBooking.query.filter_by(
                activity_id=booking.activity_id,
                status='booked'
            ).count()

            booking_info = {
                'id': booking.id,
                'activity_id': booking.activity_id,
                'activity_title': activity.title if activity else '活动已删除',
                'activity_description': activity.description if activity else None,
                'activity_location': activity.location if activity else None,
                'activity_start_time': activity.start_time.isoformat().replace('+00:00', 'Z') if activity else None,
                'activity_end_time': activity.end_time.isoformat().replace('+00:00', 'Z') if activity else None,
                'activity_max_participants': activity.max_participants if activity else None,
                'activity_current_participants': current_booked,
                'activity_organizer_display': activity.organizer_display if activity else None,
                'activity_tags': activity.tags if activity else [],
                'activity_status': activity.status if activity else None,
                'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z'),
                'status': booking.status,
                'notes': booking.notes,
                'updated_at': booking.updated_at.isoformat().replace('+00:00', 'Z') if booking.updated_at else None
            }
            bookings_data.append(booking_info)

        # 手动分页（考虑活动状态筛选）
        filtered_total = len(bookings_data)
        start = (page - 1) * size
        end = start + size
        paginated_data = bookings_data[start:end]

        return ResponseService.success({
            'total': filtered_total,
            'page': page,
            'size': size,
            'items': paginated_data
        }, message='预约列表获取成功')

    except Exception as e:
        return ResponseService.error(f'获取预约列表失败: {str(e)}', status_code=500)


@booking_bp.route('/bookings/<int:booking_id>/status', methods=['PUT'])
@token_required
def update_booking_status(current_user, booking_id):
    """更新预约状态（管理员/组织者操作）"""
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        new_status = data.get('status')
        notes = data.get('notes', '')

        if not new_status:
            return ResponseService.error('状态不能为空', status_code=400)

        # 验证状态值
        valid_statuses = ['booked', 'cancelled', 'attended', 'absent']
        if new_status not in valid_statuses:
            return ResponseService.error(f'无效的状态值，支持的值: {", ".join(valid_statuses)}', status_code=400)

        # 查找预约记录
        booking = ActivityBooking.query.get(booking_id)
        if not booking:
            return ResponseService.error('预约记录不存在', status_code=404)

        # 验证活动权限
        activity = Activity.query.get(booking.activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限修改此活动的预约状态', status_code=403)

        old_status = booking.status
        booking.status = new_status
        booking.notes = notes
        booking.updated_at = datetime.now()
        db.session.commit()

        print(f"【预约状态更新】预约ID: {booking_id}, 状态: {old_status} -> {new_status}")

        return ResponseService.success({
            'booking_id': booking_id,
            'activity_id': booking.activity_id,
            'old_status': old_status,
            'new_status': new_status,
            'notes': notes,
            'updated_time': booking.updated_at.isoformat().replace('+00:00', 'Z')
        }, message='预约状态更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'更新预约状态失败: {str(e)}', status_code=500)


@booking_bp.route('/activities/<int:activity_id>/bookings/batch', methods=['POST'])
@token_required
def batch_update_bookings(current_user, activity_id):
    """批量操作预约（管理员/组织者操作）"""
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        operation = data.get('operation')  # confirm_attendance/mark_absent/cancel
        booking_ids = data.get('booking_ids', [])

        if not operation:
            return ResponseService.error('操作类型不能为空', status_code=400)

        if not booking_ids:
            return ResponseService.error('预约ID列表不能为空', status_code=400)

        # 验证操作类型
        operation_map = {
            'confirm_attendance': 'attended',
            'mark_absent': 'absent',
            'cancel': 'cancelled'
        }

        if operation not in operation_map:
            return ResponseService.error(f'无效的操作类型，支持的值: {", ".join(operation_map.keys())}', status_code=400)

        # 验证活动权限
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限批量操作此活动的预约', status_code=403)

        # 查询要操作的预约
        bookings = ActivityBooking.query.filter(
            ActivityBooking.id.in_(booking_ids),
            ActivityBooking.activity_id == activity_id
        ).all()

        if not bookings:
            return ResponseService.error('未找到可操作的预约记录', status_code=404)

        new_status = operation_map[operation]
        success_count = 0
        error_count = 0
        errors = []

        for booking in bookings:
            try:
                old_status = booking.status
                booking.status = new_status
                booking.updated_at = datetime.now()
                success_count += 1
                print(f"【批量操作预约】预约ID: {booking.id}, 状态: {old_status} -> {new_status}")

            except Exception as e:
                error_count += 1
                errors.append(f"预约ID {booking.id}: {str(e)}")

        if success_count > 0:
            db.session.commit()

        return ResponseService.success({
            'operation': operation,
            'activity_id': activity_id,
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors
        }, message=f'批量操作完成，成功: {success_count} 个，失败: {error_count} 个')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'批量操作失败: {str(e)}', status_code=500)


@booking_bp.route('/activities/<int:activity_id>/bookings/statistics', methods=['GET'])
@token_required
def get_booking_statistics_route(current_user, activity_id):
    """获取活动预约统计（管理员/组织者操作）"""
    try:
        # 验证活动权限
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限查看此活动的预约统计', status_code=403)

        # 获取统计信息
        statistics = ActivityStatistics.get_booking_statistics(activity_id)

        return ResponseService.success(data=statistics, message='预约统计查询成功')

    except ValueError as e:
        return ResponseService.error(str(e), status_code=404)
    except Exception as e:
        return ResponseService.error(f'预约统计查询失败: {str(e)}', status_code=500)


@booking_bp.route('/activities/<int:activity_id>/availability', methods=['GET'])
def check_availability(activity_id):
    """检查活动预约可用性（无需认证）"""
    try:
        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 验证活动是否可预约
        can_book, error_msg = ActivityValidator.is_activity_bookable(activity)

        # 获取当前预约统计
        try:
            statistics = ActivityStatistics.get_booking_statistics(activity_id)
        except ValueError:
            statistics = {
                'activity_id': activity_id,
                'total_bookings': 0,
                'current_booked': 0,
                'max_participants': activity.max_participants
            }

        availability = {
            'activity_id': activity_id,
            'title': activity.title,
            'status': activity.status,
            'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'max_participants': activity.max_participants,
            'current_booked': statistics.get('current_booked', 0),
            'available_spots': statistics.get('available_spots', None),
            'is_bookable': can_book,
            'error_message': error_msg if not can_book else None,
            'booking_deadline': activity.end_time.isoformat().replace('+00:00', 'Z') if activity.end_time else None
        }

        return ResponseService.success(data=availability, message='可用性查询成功')

    except Exception as e:
        return ResponseService.error(f'可用性查询失败: {str(e)}', status_code=500)


@booking_bp.route('/bookings/<int:booking_id>', methods=['GET'])
@token_required
def get_booking_detail(current_user, booking_id):
    """获取预约详情"""
    try:
        booking = ActivityBooking.query.get(booking_id)
        if not booking:
            return ResponseService.error('预约记录不存在', status_code=404)

        # 验证权限：用户只能查看自己的预约，或组织者可以查看所有预约
        activity = Activity.query.get(booking.activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if booking.user_account != current_user.account and activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限查看此预约记录', status_code=403)

        # 获取用户信息
        user = User.query.filter_by(account=booking.user_account, is_deleted=0).first()

        # 获取当前预约人数
        current_booked = ActivityBooking.query.filter_by(
            activity_id=booking.activity_id,
            status='booked'
        ).count()

        booking_data = {
            'id': booking.id,
            'activity_id': booking.activity_id,
            'activity_title': activity.title,
            'activity_description': activity.description,
            'activity_location': activity.location,
            'activity_start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'activity_end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'activity_max_participants': activity.max_participants,
            'activity_current_participants': current_booked,
            'activity_status': activity.status,
            'user_account': booking.user_account,
            'user_display': user.username if user else '用户已注销',
            'user_avatar': user.avatar if user else None,
            'user_phone': user.phone if (user and activity.organizer_user_id == current_user.id) else None,  # 只有组织者能看到手机号
            'user_email': user.email if (user and activity.organizer_user_id == current_user.id) else None,    # 只有组织者能看到邮箱
            'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z'),
            'status': booking.status,
            'notes': booking.notes,
            'updated_at': booking.updated_at.isoformat().replace('+00:00', 'Z') if booking.updated_at else None
        }

        return ResponseService.success(data=booking_data, message='预约详情查询成功')

    except Exception as e:
        return ResponseService.error(f'预约详情查询失败: {str(e)}', status_code=500)


@booking_bp.route('/bookings/<int:booking_id>', methods=['DELETE'])
@token_required
def delete_booking(current_user, booking_id):
    """删除预约记录（仅管理员/组织者）"""
    try:
        booking = ActivityBooking.query.get(booking_id)
        if not booking:
            return ResponseService.error('预约记录不存在', status_code=404)

        # 验证活动权限
        activity = Activity.query.get(booking.activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限删除此预约记录', status_code=403)

        # 记录删除信息
        deleted_info = {
            'booking_id': booking_id,
            'activity_id': booking.activity_id,
            'user_account': booking.user_account,
            'status': booking.status,
            'deleted_time': datetime.now().isoformat().replace('+00:00', 'Z'),
            'deleted_by': current_user.account
        }

        db.session.delete(booking)
        db.session.commit()

        print(f"【预约记录删除】预约ID: {booking_id}, 操作者: {current_user.account}")

        return ResponseService.success(data=deleted_info, message='预约记录删除成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'删除预约记录失败: {str(e)}', status_code=500)


@booking_bp.route('/activities/<int:activity_id>/export/bookings', methods=['GET'])
@token_required
def export_bookings(current_user, activity_id):
    """导出活动预约列表（管理员/组织者操作）"""
    try:
        # 验证活动权限
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限导出此活动的预约列表', status_code=403)

        status = request.args.get('status', '').strip()

        # 构建查询
        query = ActivityBooking.query.filter_by(activity_id=activity_id)
        if status:
            query = query.filter(ActivityBooking.status == status)

        # 获取所有预约记录
        bookings = query.order_by(ActivityBooking.booking_time.desc()).all()

        export_data = []
        for booking in bookings:
            # 获取用户信息
            user = User.query.filter_by(account=booking.user_account, is_deleted=0).first()

            booking_data = {
                '预约ID': booking.id,
                '活动ID': booking.activity_id,
                '活动标题': activity.title,
                '用户账号': booking.user_account,
                '用户姓名': user.username if user else '用户已注销',
                '用户手机': user.phone if user else '',
                '用户邮箱': user.email if user else '',
                '预约时间': booking.booking_time.strftime('%Y-%m-%d %H:%M:%S'),
                '预约状态': booking.status,
                '备注': booking.notes or '',
                '更新时间': booking.updated_at.strftime('%Y-%m-%d %H:%M:%S') if booking.updated_at else ''
            }
            export_data.append(booking_data)

        export_info = {
            'activity_id': activity_id,
            'activity_title': activity.title,
            'export_time': datetime.now().isoformat().replace('+00:00', 'Z'),
            'total_count': len(export_data),
            'data': export_data
        }

        return ResponseService.success(data=export_info, message='预约列表导出成功')

    except Exception as e:
        return ResponseService.error(f'导出失败: {str(e)}', status_code=500)


# ------------------------------------------------------------------------------
# 3.5 discussion_bp - 讨论路由 (原 discussion/discuss.py)
# ------------------------------------------------------------------------------

discussion_bp = Blueprint('discussion', __name__, url_prefix='/api/activities/discussion')


@discussion_bp.route('/activities/<int:activity_id>/discussions', methods=['POST'])
@token_required
def create_discussion(current_user, activity_id):
    """创建活动讨论"""
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        content = data.get('content', '').strip()
        image_urls = data.get('image_urls', [])

        if not content:
            return ResponseService.error('讨论内容不能为空', status_code=400)

        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 创建讨论
        discussion = ActivityDiscuss(
            activity_id=activity_id,
            content=content,
            image_urls=image_urls if image_urls else None
        )
        # 设置发布者信息
        discussion.set_author_info(current_user)

        db.session.add(discussion)
        db.session.commit()

        print(f"【讨论创建成功】讨论ID: {discussion.id}, 用户: {current_user.account}")

        discussion_data = {
            'id': discussion.id,
            'activity_id': discussion.activity_id,
            'content': discussion.content,
            'author_user_id': discussion.author_user_id,
            'author_display': discussion.author_display,
            'author_avatar': discussion.author_avatar,
            'image_urls': discussion.image_urls or [],
            'create_time': discussion.create_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=discussion_data, message='讨论发表成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'讨论发表失败: {str(e)}', status_code=500)


@discussion_bp.route('/activities/<int:activity_id>/discussions', methods=['GET'])
def get_activity_discussions(activity_id):
    """获取活动讨论列表（无需登录）"""
    try:
        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        sort_by = request.args.get('sort_by', 'latest')  # latest/latest_comment/hottest

        # 分页查询讨论
        query = ActivityDiscuss.query.filter_by(activity_id=activity_id)

        # 排序
        if sort_by == 'latest':
            query = query.order_by(ActivityDiscuss.create_time.desc())
        elif sort_by == 'latest_comment':
            # 按最新评论时间排序（简化版，这里按讨论更新时间）
            query = query.order_by(ActivityDiscuss.update_time.desc())
        elif sort_by == 'hottest':
            # 按评论数量排序（需要关联查询）
            query = query.order_by(text("(SELECT COUNT(*) FROM activity_discuss_comment WHERE discuss_id = activity_discuss.id) DESC"))

        pagination = query.paginate(page=page, per_page=size)
        discussions = pagination.items
        total = pagination.total

        discussions_list = []
        for discussion in discussions:
            # 获取讨论的留言数量
            comment_count = ActivityDiscussComment.query.filter_by(discuss_id=discussion.id).count()

            # 获取最新评论时间
            latest_comment = ActivityDiscussComment.query.filter_by(discuss_id=discussion.id).order_by(
                ActivityDiscussComment.create_time.desc()
            ).first()

            item = {
                'id': discussion.id,
                'activity_id': discussion.activity_id,
                'content': discussion.content,
                'author_display': discussion.author_display,
                'author_avatar': discussion.author_avatar,
                'image_urls': discussion.image_urls or [],
                'comment_count': comment_count,
                'latest_comment_time': latest_comment.create_time.isoformat().replace('+00:00', 'Z') if latest_comment else None,
                'create_time': discussion.create_time.isoformat().replace('+00:00', 'Z'),
                'update_time': discussion.update_time.isoformat().replace('+00:00', 'Z')
            }
            discussions_list.append(item)

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'sort_by': sort_by,
            'items': discussions_list
        }, message='讨论列表查询成功')

    except Exception as e:
        return ResponseService.error(f'查询失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/<int:discussion_id>', methods=['GET'])
def get_discussion_detail(discussion_id):
    """获取讨论详情（无需登录）"""
    try:
        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        # 获取活动的详细信息
        activity = Activity.query.get(discussion.activity_id)

        # 获取讨论的留言列表
        comments = ActivityDiscussComment.query.filter_by(discuss_id=discussion_id).order_by(
            ActivityDiscussComment.create_time.asc()
        ).all()

        # 构建嵌套评论结构
        comments_dict = {}
        root_comments = []

        for comment in comments:
            comment_data = {
                'id': comment.id,
                'discuss_id': comment.discuss_id,
                'content': comment.content,
                'author_display': comment.author_display,
                'author_avatar': comment.author_avatar,
                'parent_comment_id': comment.parent_comment_id,
                'create_time': comment.create_time.isoformat().replace('+00:00', 'Z'),
                'replies': []
            }
            comments_dict[comment.id] = comment_data

            if comment.parent_comment_id is None:
                root_comments.append(comment_data)
            else:
                if comment.parent_comment_id in comments_dict:
                    comments_dict[comment.parent_comment_id]['replies'].append(comment_data)

        discussion_data = {
            'id': discussion.id,
            'activity_id': discussion.activity_id,
            'activity_title': activity.title if activity else '活动已删除',
            'content': discussion.content,
            'author_display': discussion.author_display,
            'author_avatar': discussion.author_avatar,
            'image_urls': discussion.image_urls or [],
            'create_time': discussion.create_time.isoformat().replace('+00:00', 'Z'),
            'update_time': discussion.update_time.isoformat().replace('+00:00', 'Z'),
            'comment_count': len(comments),
            'comments': root_comments  # 嵌套结构的评论
        }

        return ResponseService.success(data=discussion_data, message='讨论详情查询成功')

    except Exception as e:
        return ResponseService.error(f'讨论详情查询失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/<int:discussion_id>', methods=['PUT'])
@token_required
def update_discussion(current_user, discussion_id):
    """更新讨论（需要认证）"""
    try:
        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        # 检查权限（只有作者可以修改）
        if discussion.author_user_id != current_user.id:
            return ResponseService.error('无权限修改此讨论', status_code=403)

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        # 更新内容
        if 'content' in data:
            new_content = data['content'].strip()
            if not new_content:
                return ResponseService.error('讨论内容不能为空', status_code=400)
            discussion.content = new_content

        if 'image_urls' in data:
            discussion.image_urls = data['image_urls']

        discussion.update_time = datetime.now()
        db.session.commit()

        print(f"【讨论更新成功】讨论ID: {discussion_id}, 用户: {current_user.account}")

        discussion_data = {
            'id': discussion.id,
            'activity_id': discussion.activity_id,
            'content': discussion.content,
            'author_display': discussion.author_display,
            'image_urls': discussion.image_urls or [],
            'create_time': discussion.create_time.isoformat().replace('+00:00', 'Z'),
            'update_time': discussion.update_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=discussion_data, message='讨论更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'讨论更新失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/<int:discussion_id>', methods=['DELETE'])
@token_required
def delete_discussion(current_user, discussion_id):
    """删除讨论（需要认证）"""
    try:
        print(f"【删除讨论请求】讨论ID: {discussion_id}, 用户: {current_user.account}")

        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        # 验证是否为讨论作者
        if discussion.author_user_id != current_user.id:
            return ResponseService.error('无权删除此讨论', status_code=403)

        # 统计即将删除的留言数量
        comment_count = ActivityDiscussComment.query.filter_by(discuss_id=discussion_id).count()

        # 删除讨论（级联删除所有相关留言）
        db.session.delete(discussion)
        db.session.commit()

        print(f"【讨论删除成功】讨论ID: {discussion_id}, 用户: {current_user.account}")
        print(f"【级联删除留言】共删除 {comment_count} 条相关留言")

        return ResponseService.success(
            data={
                'id': discussion_id,
                'deleted_comment_count': comment_count
            },
            message='讨论删除成功，所有相关留言已删除'
        )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'讨论删除失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/<int:discussion_id>/comments', methods=['POST'])
@token_required
def create_comment(current_user, discussion_id):
    """创建讨论留言"""
    try:
        print(f"【创建讨论留言请求】讨论ID: {discussion_id}, 用户: {current_user.account}")

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        content = data.get('content', '').strip()
        parent_comment_id = data.get('parent_comment_id')  # 可选，用于回复留言

        if not content:
            return ResponseService.error('留言内容不能为空', status_code=400)

        # 验证讨论是否存在
        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        # 如果是回复留言，验证父留言是否存在
        if parent_comment_id:
            parent_comment = ActivityDiscussComment.query.get(parent_comment_id)
            if not parent_comment or parent_comment.discuss_id != discussion_id:
                return ResponseService.error('父留言不存在或不属于该讨论', status_code=404)

        # 创建留言
        comment = ActivityDiscussComment(
            discuss_id=discussion_id,
            content=content,
            parent_comment_id=parent_comment_id if parent_comment_id else None
        )
        # 设置发布者信息
        comment.set_author_info(current_user)

        db.session.add(comment)
        db.session.commit()

        print(f"【讨论留言成功】留言ID: {comment.id}, 用户: {current_user.account}")

        comment_data = {
            'id': comment.id,
            'discuss_id': comment.discuss_id,
            'content': comment.content,
            'author_user_id': comment.author_user_id,
            'author_display': comment.author_display,
            'author_avatar': comment.author_avatar,
            'parent_comment_id': comment.parent_comment_id,
            'create_time': comment.create_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=comment_data, message='留言发表成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'留言发表失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/<int:discussion_id>/comments', methods=['GET'])
def get_discussion_comments(discussion_id):
    """获取讨论留言列表（无需登录）"""
    try:
        print(f"【讨论留言列表查询】讨论ID: {discussion_id}")

        # 验证讨论是否存在
        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        sort_by = request.args.get('sort_by', 'oldest')  # oldest/latest

        # 获取所有留言
        query = ActivityDiscussComment.query.filter_by(discuss_id=discussion_id)

        # 排序
        if sort_by == 'latest':
            query = query.order_by(ActivityDiscussComment.create_time.desc())
        else:  # oldest
            query = query.order_by(ActivityDiscussComment.create_time.asc())

        # 分页查询
        pagination = query.paginate(page=page, per_page=size)
        comments = pagination.items
        total = pagination.total

        comments_list = []
        for comment in comments:
            # 获取回复数量
            reply_count = ActivityDiscussComment.query.filter_by(
                parent_comment_id=comment.id
            ).count()

            comment_data = {
                'id': comment.id,
                'discuss_id': comment.discuss_id,
                'content': comment.content,
                'author_display': comment.author_display,
                'author_avatar': comment.author_avatar,
                'parent_comment_id': comment.parent_comment_id,
                'reply_count': reply_count,
                'create_time': comment.create_time.isoformat().replace('+00:00', 'Z')
            }
            comments_list.append(comment_data)

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'sort_by': sort_by,
            'items': comments_list
        }, message="留言列表查询成功")

    except Exception as e:
        return ResponseService.error(f'留言列表查询失败: {str(e)}', status_code=500)


@discussion_bp.route('/comments/<int:comment_id>', methods=['PUT'])
@token_required
def update_comment(current_user, comment_id):
    """更新讨论留言"""
    try:
        comment = ActivityDiscussComment.query.get(comment_id)
        if not comment:
            return ResponseService.error('留言不存在', status_code=404)

        # 检查权限（只有作者可以修改）
        if comment.author_user_id != current_user.id:
            return ResponseService.error('无权限修改此留言', status_code=403)

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        # 更新内容
        if 'content' in data:
            new_content = data['content'].strip()
            if not new_content:
                return ResponseService.error('留言内容不能为空', status_code=400)
            comment.content = new_content

        comment.update_time = datetime.now()
        db.session.commit()

        print(f"【留言更新成功】留言ID: {comment_id}, 用户: {current_user.account}")

        comment_data = {
            'id': comment.id,
            'discuss_id': comment.discuss_id,
            'content': comment.content,
            'author_display': comment.author_display,
            'parent_comment_id': comment.parent_comment_id,
            'create_time': comment.create_time.isoformat().replace('+00:00', 'Z'),
            'update_time': comment.update_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=comment_data, message='留言更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'留言更新失败: {str(e)}', status_code=500)


@discussion_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
@token_required
def delete_comment(current_user, comment_id):
    """删除讨论留言（层级删除逻辑）"""
    try:
        print(f"【删除讨论留言请求】留言ID: {comment_id}, 用户: {current_user.account}")

        comment = ActivityDiscussComment.query.get(comment_id)
        if not comment:
            return ResponseService.error('留言不存在', status_code=404)

        # 验证是否为留言作者
        if comment.author_user_id != current_user.id:
            return ResponseService.error('无权删除此留言', status_code=403)

        # 层级删除逻辑：将子留言的parent_comment_id设为NULL
        child_comments = ActivityDiscussComment.query.filter_by(parent_comment_id=comment_id).all()
        for child_comment in child_comments:
            child_comment.parent_comment_id = None
            print(f"【子留言处理】子留言ID: {child_comment.id} 的parent_comment_id设为NULL")

        # 删除目标留言
        db.session.delete(comment)
        db.session.commit()

        print(f"【讨论留言删除成功】留言ID: {comment_id}, 用户: {current_user.account}")
        print(f"【子留言保留】共保留 {len(child_comments)} 条子留言")

        return ResponseService.success(
            data={
                'id': comment_id,
                'preserved_child_count': len(child_comments)
            },
            message='留言删除成功，子留言已保留'
        )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'留言删除失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/<int:discussion_id>/comments/nested', methods=['GET'])
def get_nested_comments(discussion_id):
    """获取嵌套结构的讨论留言（无需登录）"""
    try:
        print(f"【嵌套留言查询】讨论ID: {discussion_id}")

        # 验证讨论是否存在
        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        # 获取所有留言，按时间正序排列（便于构建嵌套结构）
        comments = ActivityDiscussComment.query.filter_by(
            discuss_id=discussion_id
        ).order_by(ActivityDiscussComment.create_time.asc()).all()

        # 构建嵌套结构
        comments_dict = {}
        root_comments = []

        for comment in comments:
            comment_data = {
                'id': comment.id,
                'discuss_id': comment.discuss_id,
                'content': comment.content,
                'author_display': comment.author_display,
                'author_avatar': comment.author_avatar,
                'parent_comment_id': comment.parent_comment_id,
                'create_time': comment.create_time.isoformat().replace('+00:00', 'Z'),
                'replies': []
            }
            comments_dict[comment.id] = comment_data

            if comment.parent_comment_id is None:
                root_comments.append(comment_data)
            else:
                if comment.parent_comment_id in comments_dict:
                    comments_dict[comment.parent_comment_id]['replies'].append(comment_data)

        return ResponseService.success({
            'discussion_id': discussion_id,
            'total_comments': len(comments),
            'root_comments_count': len(root_comments),
            'comments': root_comments
        }, message="嵌套留言查询成功")

    except Exception as e:
        return ResponseService.error(f'嵌套留言查询失败: {str(e)}', status_code=500)


@discussion_bp.route('/activities/<int:activity_id>/discussions/search', methods=['GET'])
def search_discussions(activity_id):
    """搜索活动讨论（无需登录）"""
    try:
        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        keyword = request.args.get('keyword', '').strip()
        if not keyword:
            return ResponseService.error('搜索关键词不能为空', status_code=400)

        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))

        # 搜索讨论
        query = ActivityDiscuss.query.filter(
            ActivityDiscuss.activity_id == activity_id,
            ActivityDiscuss.content.like(f'%{keyword}%')
        ).order_by(ActivityDiscuss.create_time.desc())

        pagination = query.paginate(page=page, per_page=size)
        discussions = pagination.items
        total = pagination.total

        discussions_list = []
        for discussion in discussions:
            # 获取讨论的留言数量
            comment_count = ActivityDiscussComment.query.filter_by(discuss_id=discussion.id).count()

            item = {
                'id': discussion.id,
                'activity_id': discussion.activity_id,
                'content': discussion.content,
                'author_display': discussion.author_display,
                'author_avatar': discussion.author_avatar,
                'image_urls': discussion.image_urls or [],
                'comment_count': comment_count,
                'create_time': discussion.create_time.isoformat().replace('+00:00', 'Z'),
                'update_time': discussion.update_time.isoformat().replace('+00:00', 'Z')
            }
            discussions_list.append(item)

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'keyword': keyword,
            'items': discussions_list
        }, message='讨论搜索成功')

    except Exception as e:
        return ResponseService.error(f'搜索失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/<int:discussion_id>/pin', methods=['PUT'])
@token_required
def pin_discussion(current_user, discussion_id):
    """置顶/取消置顶讨论（管理员操作）"""
    try:
        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        # 验证活动权限
        activity = Activity.query.get(discussion.activity_id)
        if not activity or activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限置顶此讨论', status_code=403)

        data = request.get_json()
        is_pinned = data.get('is_pinned', True)

        # 这里可以添加置顶字段的逻辑
        # 当前数据库模型可能没有置顶字段，这里提供接口框架

        pin_info = {
            'discussion_id': discussion_id,
            'is_pinned': is_pinned,
            'pin_time': datetime.now().isoformat().replace('+00:00', 'Z') if is_pinned else None,
            'operator': current_user.account
        }

        return ResponseService.success(data=pin_info, message=f'讨论已{"置顶" if is_pinned else "取消置顶"}')

    except Exception as e:
        return ResponseService.error(f'置顶操作失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/statistics', methods=['GET'])
@token_required
def get_discussion_statistics(current_user):
    """获取讨论统计（管理员操作）"""
    try:
        # 获取用户创建的活动
        user_activities = Activity.query.filter_by(organizer_user_id=current_user.id).all()
        activity_ids = [activity.id for activity in user_activities]

        if not activity_ids:
            return ResponseService.success({
                'total_discussions': 0,
                'total_comments': 0,
                'activities_with_discussions': 0,
                'activities': []
            }, message='讨论统计查询成功')

        # 讨论统计
        discussion_stats = db.session.execute(text("""
            SELECT
                COUNT(*) as total_discussions,
                COUNT(DISTINCT activity_id) as activities_with_discussions
            FROM activity_discuss
            WHERE activity_id IN :activity_ids
        """), {"activity_ids": tuple(activity_ids)}).fetchone()

        # 评论统计
        comment_stats = db.session.execute(text("""
            SELECT COUNT(*) as total_comments
            FROM activity_discuss_comment adc
            JOIN activity_discuss ad ON adc.discuss_id = ad.id
            WHERE ad.activity_id IN :activity_ids
        """), {"activity_ids": tuple(activity_ids)}).fetchone()

        # 各活动讨论统计
        activity_stats = db.session.execute(text("""
            SELECT
                a.id,
                a.title,
                COUNT(DISTINCT ad.id) as discussion_count,
                COUNT(adc.id) as comment_count
            FROM activities a
            LEFT JOIN activity_discuss ad ON a.id = ad.activity_id
            LEFT JOIN activity_discuss_comment adc ON ad.id = adc.discuss_id
            WHERE a.id IN :activity_ids
            GROUP BY a.id, a.title
            ORDER BY discussion_count DESC, comment_count DESC
        """), {"activity_ids": tuple(activity_ids)}).fetchall()

        activities_data = []
        for stat in activity_stats:
            activities_data.append({
                'activity_id': stat.id,
                'activity_title': stat.title,
                'discussion_count': stat.discussion_count,
                'comment_count': stat.comment_count
            })

        statistics = {
            'user_id': current_user.id,
            'total_discussions': discussion_stats.total_discussions or 0,
            'total_comments': comment_stats.total_comments or 0,
            'activities_with_discussions': discussion_stats.activities_with_discussions or 0,
            'total_activities': len(activity_ids),
            'activities': activities_data,
            'updated_at': datetime.now().isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=statistics, message='讨论统计查询成功')

    except Exception as e:
        return ResponseService.error(f'统计查询失败: {str(e)}', status_code=500)


# ------------------------------------------------------------------------------
# 3.6 bp_activities_public - 公开访问路由 (原 public/activity.py)
# ------------------------------------------------------------------------------

bp_activities_public = Blueprint('activities_public', __name__, url_prefix='/api/public/activities')


@bp_activities_public.route('/activities', methods=['GET'])
def get_public_activities():
    """获取公开的活动列表（无需登录）"""
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        keyword = request.args.get('keyword', '').strip()
        organizer_display = request.args.get('organizer_display', '').strip()
        status = request.args.get('status', 'published')  # 默认只显示已发布的活动
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        # 构建查询
        query = Activity.query

        # 状态筛选
        if status:
            query = query.filter(Activity.status == status)

        # 关键词搜索（标题和描述）
        if keyword:
            query = query.filter(
                (Activity.title.like(f'%{keyword}%')) |
                (Activity.description.like(f'%{keyword}%'))
            )

        # 组织者筛选
        if organizer_display:
            query = query.filter(Activity.organizer_display.like(f'%{organizer_display}%'))

        # 时间范围筛选
        if start_date:
            try:
                start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(Activity.start_time >= start_datetime)
            except ValueError:
                pass  # 忽略无效的日期格式

        if end_date:
            try:
                end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(Activity.end_time <= end_datetime)
            except ValueError:
                pass  # 忽略无效的日期格式

        # 分页查询（按开始时间倒序，即将开始的活动在前）
        pagination = query.order_by(Activity.start_time.asc()).paginate(page=page, per_page=size)
        activities = pagination.items
        total = pagination.total

        result_list = []
        for activity in activities:
            # 计算活动状态
            now = datetime.utcnow()
            if activity.start_time > now:
                activity_status = "即将开始"
            elif activity.end_time >= now:
                activity_status = "进行中"
            else:
                activity_status = "已结束"

            # 获取报名人数（如果有预约表的话）
            try:
                booking_count = ActivityBooking.query.filter_by(
                    activity_id=activity.id,
                    status='confirmed'
                ).count()
            except:
                booking_count = 0

            item = {
                'id': activity.id,
                'title': activity.title,
                'description': activity.description[:200] + '...' if len(activity.description) > 200 else activity.description,
                'organizer_display': activity.organizer_display,
                'location': activity.location,
                'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
                'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
                'max_participants': activity.max_participants,
                'current_participants': booking_count,
                'activity_status': activity_status,
                'status': activity.status,
                'created_at': activity.created_at.isoformat().replace('+00:00', 'Z')
            }
            result_list.append(item)

        return ResponseService.paginated_success(
            items=result_list,
            total=total,
            page=page,
            size=size,
            message="活动列表查询成功"
        )

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_activities_public.route('/activities/<int:activity_id>', methods=['GET'])
def get_public_activity_detail(activity_id):
    """获取公开的活动详情（无需登录）"""
    try:
        activity = Activity.query.filter_by(id=activity_id, status='published').first()
        if not activity:
            return ResponseService.error('活动不存在或未发布', status_code=404)

        # 获取报名人数
        try:
            booking_count = ActivityBooking.query.filter_by(
                activity_id=activity.id,
                status='confirmed'
            ).count()
        except:
            booking_count = 0

        # 计算活动状态
        now = datetime.utcnow()
        if activity.start_time > now:
            activity_status = "即将开始"
            days_until = (activity.start_time - now).days
            status_info = f"距离开始还有 {days_until} 天"
        elif activity.end_time >= now:
            activity_status = "进行中"
            status_info = "活动正在进行中"
        else:
            activity_status = "已结束"
            status_info = "活动已结束"

        # 检查是否还可以报名
        can_book = (
            activity_status == "即将开始" and
            activity.max_participants and
            booking_count < activity.max_participants
        )

        # 返回完整信息
        item = {
            'id': activity.id,
            'title': activity.title,
            'description': activity.description,
            'organizer_display': activity.organizer_display,
            'location': activity.location,
            'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'max_participants': activity.max_participants,
            'current_participants': booking_count,
            'available_slots': max(0, activity.max_participants - booking_count) if activity.max_participants else None,
            'activity_status': activity_status,
            'status_info': status_info,
            'can_book': can_book,
            'status': activity.status,
            'created_at': activity.created_at.isoformat().replace('+00:00', 'Z'),
            'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z') if activity.updated_at else None
        }

        return ResponseService.success(data=item, message="活动详情查询成功")

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_activities_public.route('/activities/statistics', methods=['GET'])
def get_public_activities_statistics():
    """获取活动公开统计信息（无需登录）"""
    try:
        # 基本统计（仅已发布活动）
        total_published = Activity.query.filter_by(status='published').count()

        # 活动状态统计
        now = datetime.utcnow()

        # 即将开始的活动
        upcoming_count = Activity.query.filter(
            Activity.status == 'published',
            Activity.start_time > now
        ).count()

        # 进行中的活动
        ongoing_count = Activity.query.filter(
            Activity.status == 'published',
            Activity.start_time <= now,
            Activity.end_time >= now
        ).count()

        # 已结束的活动
        completed_count = Activity.query.filter(
            Activity.status == 'published',
            Activity.end_time < now
        ).count()

        # 最近30天发布的活动
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_count = Activity.query.filter(
            Activity.status == 'published',
            Activity.created_at >= thirty_days_ago
        ).count()

        # 获取报名统计（如果有预约表）
        try:
            booking_stats = db.session.query(
                func.count(ActivityBooking.id).label('total_bookings'),
                func.count(func.distinct(ActivityBooking.user_id)).label('unique_participants')
            ).filter(ActivityBooking.status == 'confirmed').first()

            total_bookings = booking_stats.total_bookings or 0
            unique_participants = booking_stats.unique_participants or 0
        except:
            total_bookings = 0
            unique_participants = 0

        statistics = {
            'total_published': total_published,
            'upcoming_count': upcoming_count,
            'ongoing_count': ongoing_count,
            'completed_count': completed_count,
            'recent_published_30days': recent_count,
            'total_bookings': total_bookings,
            'unique_participants': unique_participants
        }

        return ResponseService.success(data=statistics, message="活动统计查询成功")

    except Exception as e:
        return ResponseService.error(f'统计查询失败：{str(e)}', status_code=500)


# ==============================================================================
# 4. 模块初始化完成提示
# ==============================================================================

print("【API_activities 模块加载完成 - routes.py】")
print("  - 工具类: ActivityValidator, ActivityStatistics, ActivityStatusManager, ActivitySearchHelper")
print("  - 蓝图: root_bp, user_ops_bp, admin_manage_bp, booking_bp, discussion_bp, bp_activities_public")
