# API_activities 公共工具模块

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import text
from components import db
from components.models import Activity, ActivityBooking, ActivityRating


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