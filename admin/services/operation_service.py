# admin/services/operation_service.py
# 统一操作服务管理类

from typing import Dict, Any
from components import db
from .user_service import AdminService, UserService
from .notice_service import NoticeService
from .content_service import ScienceArticleService, ActivityService
from .forum_service import (
    ForumPostService, ForumCommentService, ActivityBookingService,
    UserLikeService, AttachmentService, ActivityRatingService
)


class OperationService:
    """统一操作服务管理类，负责根据表名选择对应的服务类"""

    def __init__(self):
        self._service_mapping = {
            'admin_info': AdminService(),
            'user_info': UserService(),
            'notice': NoticeService(),
            'science_articles': ScienceArticleService(),
            'activities': ActivityService(),
            'activity': ActivityService(),  # 支持单数形式
            'forum_posts': ForumPostService(),
            'activity_bookings': ActivityBookingService(),
            'forum_comments': ForumCommentService(),
            'user_likes': UserLikeService(),
            'attachments': AttachmentService(),
            'activity_rating': ActivityRatingService()
        }

    def get_service(self, table_name: str):
        """根据表名获取对应的服务实例"""
        if table_name not in self._service_mapping:
            raise Exception(f'不支持的表：{table_name}')
        return self._service_mapping[table_name]

    def execute_operation(self, current_user, data: Dict[str, Any]) -> Dict[str, Any]:
        """执行具体的数据库操作"""
        try:
            table_name = data['table_name']
            operate_type = data['operate_type'].lower()
            kwargs = data.get('kwargs', {})

            # 获取对应的服务
            service = self.get_service(table_name)

            # 根据操作类型调用对应方法
            if operate_type == 'add':
                return self._handle_add_operation(table_name, service, kwargs)

            elif operate_type == 'delete':
                return self._handle_delete_operation(table_name, service, kwargs)

            elif operate_type in ['update', 'edit']:
                return self._handle_update_operation(table_name, service, data, operate_type)

            elif operate_type in ['list', 'query']:
                return self._handle_query_operation(table_name, service, data, operate_type)

            elif operate_type == 'detail':
                record_id = data.get('id')
                if not record_id:
                    raise Exception('详情查询缺少参数：id')
                return service.get_record_by_id(int(record_id))

            else:
                raise Exception(f'不支持的操作类型：{operate_type}')

        except Exception as e:
            db.session.rollback()
            print(f"【操作异常】{str(e)}")
            raise Exception(f'操作失败：{str(e)}')

    def _handle_add_operation(self, table_name: str, service, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """处理新增操作"""
        if table_name == 'admin_info':
            return service.create_admin(kwargs)
        elif table_name == 'user_info':
            return service.create_user(kwargs)
        elif table_name == 'notice':
            return service.create_notice(kwargs)
        elif table_name == 'science_articles':
            return service.create_article(kwargs)
        elif table_name in ['activities', 'activity']:
            return service.create_activity(kwargs)
        elif table_name == 'forum_posts':
            return service.create_forum_post(kwargs)
        elif table_name == 'activity_bookings':
            return service.create_activity_booking(kwargs)
        elif table_name == 'forum_comments':
            return service.create_forum_comment(kwargs)
        elif table_name == 'user_likes':
            return service.create_user_like(kwargs)
        elif table_name == 'attachments':
            return service.create_attachment(kwargs)
        elif table_name == 'activity_rating':
            return service.create_activity_rating(kwargs)
        else:
            return service.create_record(kwargs)

    def _handle_delete_operation(self, table_name: str, service, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """处理删除操作"""
        if table_name in ['admin_info', 'user_info']:
            return service.delete_admin(kwargs) if table_name == 'admin_info' else service.delete_user(kwargs)
        elif table_name == 'notice':
            return service.delete_notice(kwargs)
        elif table_name in ['activities', 'activity']:
            return service.delete_activity(kwargs)
        else:
            return service.delete_record(kwargs)

    def _handle_update_operation(self, table_name: str, service, data: Dict[str, Any], operate_type: str) -> Dict[str, Any]:
        """处理更新操作"""
        if table_name == 'admin_info':
            record_id = data.get('id')
            update_kwargs = data.get('kwargs', {}).copy()
            return service.update_admin(record_id, update_kwargs)
        elif table_name == 'user_info':
            record_id = data.get('id')
            update_kwargs = data.get('kwargs', {}).copy()
            return service.update_user(record_id, update_kwargs)
        elif table_name == 'notice':
            return service.update_notice(operate_type, **data)
        elif table_name == 'science_articles':
            return service.update_article(operate_type, **data)
        elif table_name in ['activities', 'activity']:
            return service.update_activity(operate_type, **data)
        elif table_name == 'forum_posts':
            return service.update_forum_post(operate_type, **data)
        else:
            # 通用更新逻辑
            if operate_type == 'edit':
                update_kwargs = data.get('kwargs', {}).copy()
                record_id = data.get('id')
                if not record_id:
                    raise Exception(f'{table_name}更新缺少主键：id')
                query_kwargs = {'id': int(record_id)}
                update_kwargs.pop('id', None)
            else:
                query_kwargs = data.get('query_kwargs', {})
                update_kwargs = data.get('update_kwargs', {})

            return service.update_record(query_kwargs, update_kwargs)

    def _handle_query_operation(self, table_name: str, service, data: Dict[str, Any], operate_type: str) -> Dict[str, Any]:
        """处理查询操作"""
        page = int(data.get('page', 1))
        size = int(data.get('size', 10))
        kwargs = data.get('kwargs', {})

        if table_name == 'admin_info':
            return service.get_admin_list(page, size, kwargs if kwargs else None)
        elif table_name == 'user_info':
            return service.get_user_list(page, size, kwargs if kwargs else None)
        elif table_name == 'notice':
            filters = kwargs.copy() if kwargs else {}
            return service.get_notice_list(page, size, filters)
        elif table_name == 'science_articles':
            filters = kwargs.copy() if kwargs else {}
            return service.get_article_list(page, size, filters)
        elif table_name in ['activities', 'activity']:
            filters = kwargs.copy() if kwargs else {}
            return service.get_activity_list(page, size, filters)
        elif table_name == 'forum_posts':
            filters = kwargs.copy() if kwargs else {}
            return service.get_forum_post_list(page, size, filters)
        elif table_name == 'activity_bookings':
            filters = kwargs.copy() if kwargs else {}
            return service.get_activity_booking_list(page, size, filters)
        elif table_name == 'forum_comments':
            filters = kwargs.copy() if kwargs else {}
            return service.get_forum_comment_list(page, size, filters)
        elif table_name == 'user_likes':
            filters = kwargs.copy() if kwargs else {}
            return service.get_user_like_list(page, size, filters)
        elif table_name == 'attachments':
            filters = kwargs.copy() if kwargs else {}
            return service.get_attachment_list(page, size, filters)
        elif table_name == 'activity_rating':
            filters = kwargs.copy() if kwargs else {}
            return service.get_activity_rating_list(page, size, filters)
        else:
            # 通用查询逻辑
            filter_kwargs = {}
            for key, value in kwargs.items():
                if hasattr(service.model_class, key) and value != '' and value is not None:
                    filter_kwargs[key] = value

            return service.get_paginated_list(page, size, filter_kwargs if filter_kwargs else None)