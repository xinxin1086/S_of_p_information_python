
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import text
from components import db
from components.models import Activity, ActivityBooking, ActivityRating


class ActivityValidator:
    

    @staticmethod
    def is_activity_bookable(activity: Activity) -> tuple[bool, str]:
        
        if not activity:
            return False, "活动不存在"

        if activity.status not in ['published']:
            return False, f"当前活动状态({activity.status})不允许预约"

        if activity.end_time and activity.end_time < datetime.utcnow():
            return False, "活动已结束，无法预约"

        if activity.status == 'cancelled':
            return False, "活动已取消，无法预约"

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
        
        existing_booking = ActivityBooking.query.filter_by(
            activity_id=activity_id,
            user_account=user_account
        ).first()

        if existing_booking and existing_booking.status == 'booked':
            return True, existing_booking

        return False, existing_booking

    @staticmethod
    def can_user_rate_activity(user_id: int, activity_id: int) -> tuple[bool, str]:
        
        activity = Activity.query.get(activity_id)
        if not activity:
            return False, "活动不存在"

        from components.models import User
        user = User.query.get(user_id)
        if not user:
            return False, "用户不存在"

        user_participated = ActivityBooking.query.filter_by(
            activity_id=activity_id,
            user_account=user.account,
            status='attended'
        ).first()

        if not user_participated:
            return False, "您需要参与活动后才能评分"

        existing_rating = ActivityRating.query.filter_by(
            activity_id=activity_id,
            rater_user_id=user_id
        ).first()

        if existing_rating:
            return False, "您已经为该活动评过分"

        return True, ""

    @staticmethod
    def is_activity_manageable(activity: Activity, user_id: int) -> tuple[bool, str]:
        
        if not activity:
            return False, "活动不存在"

        if activity.organizer_user_id != user_id:
            return False, "无权限管理此活动"

        return True, ""


class ActivityStatistics:
    

    @staticmethod
    def get_booking_statistics(activity_id: int) -> Dict[str, Any]:
        
        activity = Activity.query.get(activity_id)
        if not activity:
            raise ValueError("活动不存在")

        stats = db.session.execute(text(), {"activity_id": activity_id}).fetchone()

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
        
        activity = Activity.query.get(activity_id)
        if not activity:
            raise ValueError("活动不存在")

        stats = db.session.execute(text(), {"activity_id": activity_id}).fetchone()

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
    

    @staticmethod
    def update_activity_status(activity: Activity, new_status: str, user_id: int = None) -> tuple[bool, str]:
        
        valid_statuses = ['draft', 'published', 'cancelled', 'completed']

        if new_status not in valid_statuses:
            return False, f"无效的活动状态，支持的值: {', '.join(valid_statuses)}"

        old_status = activity.status
        status_transitions = {
            'draft': ['published', 'cancelled'],
            'published': ['cancelled', 'completed'],
            'cancelled': [],
            'completed': []
        }

        if new_status not in status_transitions.get(old_status, []):
            return False, f"无法从状态 '{old_status}' 转换到 '{new_status}'"

        if new_status == 'completed':
            if activity.end_time and activity.end_time > datetime.utcnow():
                return False, "活动尚未结束，无法标记为完成"

        activity.status = new_status
        activity.updated_at = datetime.utcnow()

        return True, f"活动状态已从 '{old_status}' 更新为 '{new_status}'"

    @staticmethod
    def get_status_flow_info() -> Dict[str, list]:
        
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
    

    @staticmethod
    def build_activity_query(filters: Dict[str, Any]) -> Any:
        
        query = Activity.query

        if 'status' in filters and filters['status']:
            query = query.filter(Activity.status == filters['status'])

        if 'organizer_user_id' in filters and filters['organizer_user_id']:
            query = query.filter(Activity.organizer_user_id == filters['organizer_user_id'])

        if 'keyword' in filters and filters['keyword']:
            keyword = f"%{filters['keyword']}%"
            query = query.filter(
                (Activity.title.like(keyword)) |
                (Activity.description.like(keyword)) |
                (Activity.location.like(keyword))
            )

        if 'tags' in filters and filters['tags']:
            for tag in filters['tags']:
                query = query.filter(Activity.tags.contains([tag]))

        if 'start_time_from' in filters and filters['start_time_from']:
            query = query.filter(Activity.start_time >= filters['start_time_from'])

        if 'start_time_to' in filters and filters['start_time_to']:
            query = query.filter(Activity.start_time <= filters['start_time_to'])

        if 'end_time_from' in filters and filters['end_time_from']:
            query = query.filter(Activity.end_time >= filters['end_time_from'])

        if 'end_time_to' in filters and filters['end_time_to']:
            query = query.filter(Activity.end_time <= filters['end_time_to'])

        return query