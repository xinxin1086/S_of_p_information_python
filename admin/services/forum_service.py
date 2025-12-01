# admin/services/forum_service.py
# 论坛管理服务类

from typing import Dict, Any
from components import db
from components.models import ForumPost, ForumComment, ActivityBooking, ActivityComment, UserLike, Attachment
from .base_service import BaseService, TimeFieldMixin


class ForumPostService(BaseService, TimeFieldMixin):
    """论坛帖子管理服务类"""

    def __init__(self):
        super().__init__(ForumPost)

    def create_forum_post(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建论坛帖子"""
        # 验证必填字段
        required_fields = ['title', 'content', 'author_account']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                raise Exception(f'缺少必填字段：{field}')

        try:
            new_record = ForumPost(
                title=data['title'],
                content=data['content'],
                author_account=data['author_account'],
                category=data.get('category', 'default'),
                status=data.get('status', 'published')
            )
            db.session.add(new_record)
            db.session.commit()

            result = {'id': new_record.id, 'message': '论坛帖子新增成功'}
            print(f"【论坛帖子创建成功】ID: {new_record.id}")
            return result
        except Exception as e:
            db.session.rollback()
            raise Exception(f'创建论坛帖子失败：{str(e)}')

    def update_forum_post(self, query_type: str = 'edit', **kwargs) -> Dict[str, Any]:
        """更新论坛帖子"""
        if query_type == 'edit':
            update_kwargs = kwargs.get('data', {}).copy()
            record_id = kwargs.get('id')
            if not record_id:
                raise Exception('论坛帖子更新缺少主键：id')
            query_kwargs = {'id': int(record_id)}
            update_kwargs.pop('id', None)
        else:
            query_kwargs = kwargs.get('query_kwargs', {})
            update_kwargs = kwargs.get('update_kwargs', {})

        return self.update_record(query_kwargs, update_kwargs)

    def get_forum_post_list(self, page: int = 1, size: int = 10,
                           filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取论坛帖子列表"""
        try:
            query = ForumPost.query

            # 论坛帖子筛选
            if filters:
                if 'author_account' in filters:
                    query = query.filter(ForumPost.author_account == filters['author_account'])
                if 'category' in filters:
                    query = query.filter(ForumPost.category == filters['category'])
                if 'status' in filters:
                    query = query.filter(ForumPost.status == filters['status'])
                if 'title' in filters:
                    query = query.filter(ForumPost.title.like(f"%{filters['title']}%"))

            return self.get_paginated_list(page, size, None, 'id')
        except Exception as e:
            raise Exception(f'查询论坛帖子列表失败：{str(e)}')


class ForumCommentService(BaseService, TimeFieldMixin):
    """论坛评论管理服务类"""

    def __init__(self):
        super().__init__(ForumComment)

    def create_forum_comment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建论坛评论"""
        # 验证必填字段
        required_fields = ['post_id', 'author_account', 'content']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                raise Exception(f'缺少必填字段：{field}')

        try:
            # 处理数字字段
            data['post_id'] = int(data['post_id'])

            new_record = ForumPost(**data)
            db.session.add(new_record)
            db.session.commit()

            result = {'id': new_record.id, 'message': 'forum_comments新增成功'}
            print(f"【{ForumComment.__tablename__}创建成功】ID: {new_record.id}")
            return result
        except Exception as e:
            db.session.rollback()
            raise Exception(f'创建论坛评论失败：{str(e)}')

    def get_forum_comment_list(self, page: int = 1, size: int = 10,
                              filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取论坛评论列表"""
        try:
            query = ForumComment.query

            # 论坛评论筛选
            if filters:
                if 'post_id' in filters:
                    query = query.filter(ForumComment.post_id == int(filters['post_id']))
                if 'author_account' in filters:
                    query = query.filter(ForumComment.author_account == filters['author_account'])

            return self.get_paginated_list(page, size, None, 'id')
        except Exception as e:
            raise Exception(f'查询论坛评论列表失败：{str(e)}')


class ActivityBookingService(BaseService, TimeFieldMixin):
    """活动预约管理服务类"""

    def __init__(self):
        super().__init__(ActivityBooking)

    def create_activity_booking(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建活动预约"""
        # 验证必填字段
        required_fields = ['activity_id', 'user_account']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                raise Exception(f'缺少必填字段：{field}')

        try:
            # 处理数字字段
            data['activity_id'] = int(data['activity_id'])

            new_record = ActivityBooking(**data)
            db.session.add(new_record)
            db.session.commit()

            result = {'id': new_record.id, 'message': 'activity_bookings新增成功'}
            print(f"【{ActivityBooking.__tablename__}创建成功】ID: {new_record.id}")
            return result
        except Exception as e:
            db.session.rollback()
            raise Exception(f'创建活动预约失败：{str(e)}')

    def get_activity_booking_list(self, page: int = 1, size: int = 10,
                                 filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取活动预约列表"""
        try:
            query = ActivityBooking.query

            # 活动预约筛选
            if filters:
                if 'activity_id' in filters:
                    query = query.filter(ActivityBooking.activity_id == int(filters['activity_id']))
                if 'user_account' in filters:
                    query = query.filter(ActivityBooking.user_account == filters['user_account'])
                if 'status' in filters:
                    query = query.filter(ActivityBooking.status == filters['status'])

            return self.get_paginated_list(page, size, None, 'id')
        except Exception as e:
            raise Exception(f'查询活动预约列表失败：{str(e)}')


class ActivityCommentService(BaseService, TimeFieldMixin):
    """活动评论管理服务类"""

    def __init__(self):
        super().__init__(ActivityComment)

    def create_activity_comment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建活动评论"""
        # 验证必填字段
        required_fields = ['activity_id', 'user_account', 'content']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                raise Exception(f'缺少必填字段：{field}')

        try:
            # 处理数字字段
            numeric_fields = ['activity_id', 'rating']
            processed_data = self.process_numeric_fields(data, numeric_fields)

            new_record = ActivityComment(**processed_data)
            db.session.add(new_record)
            db.session.commit()

            result = {'id': new_record.id, 'message': 'activity_comments新增成功'}
            print(f"【{ActivityComment.__tablename__}创建成功】ID: {new_record.id}")
            return result
        except Exception as e:
            db.session.rollback()
            raise Exception(f'创建活动评论失败：{str(e)}')

    def get_activity_comment_list(self, page: int = 1, size: int = 10,
                                 filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取活动评论列表"""
        try:
            query = ActivityComment.query

            # 活动评论筛选
            if filters:
                if 'activity_id' in filters:
                    query = query.filter(ActivityComment.activity_id == int(filters['activity_id']))
                if 'user_account' in filters:
                    query = query.filter(ActivityComment.user_account == filters['user_account'])

            return self.get_paginated_list(page, size, None, 'id')
        except Exception as e:
            raise Exception(f'查询活动评论列表失败：{str(e)}')


class UserLikeService(BaseService, TimeFieldMixin):
    """用户点赞管理服务类"""

    def __init__(self):
        super().__init__(UserLike)

    def create_user_like(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建用户点赞"""
        # 验证必填字段
        required_fields = ['user_account', 'target_type', 'target_id']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                raise Exception(f'缺少必填字段：{field}')

        try:
            # 处理数字字段
            numeric_fields = ['target_id']
            processed_data = self.process_numeric_fields(data, numeric_fields)

            new_record = UserLike(**processed_data)
            db.session.add(new_record)
            db.session.commit()

            result = {'id': new_record.id, 'message': 'user_likes新增成功'}
            print(f"【{UserLike.__tablename__}创建成功】ID: {new_record.id}")
            return result
        except Exception as e:
            db.session.rollback()
            raise Exception(f'创建用户点赞失败：{str(e)}')

    def get_user_like_list(self, page: int = 1, size: int = 10,
                          filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取用户点赞列表"""
        try:
            query = UserLike.query

            # 用户点赞筛选
            if filters:
                if 'user_account' in filters:
                    query = query.filter(UserLike.user_account == filters['user_account'])
                if 'target_type' in filters:
                    query = query.filter(UserLike.target_type == filters['target_type'])
                if 'target_id' in filters:
                    query = query.filter(UserLike.target_id == int(filters['target_id']))

            return self.get_paginated_list(page, size, None, 'id')
        except Exception as e:
            raise Exception(f'查询用户点赞列表失败：{str(e)}')


class AttachmentService(BaseService, TimeFieldMixin):
    """附件管理服务类"""

    def __init__(self):
        super().__init__(Attachment)

    def create_attachment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建附件"""
        # 验证必填字段
        required_fields = ['uploader_account', 'file_name', 'file_path', 'file_size', 'file_type', 'usage_type']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                raise Exception(f'缺少必填字段：{field}')

        try:
            # 处理数字字段
            numeric_fields = ['file_size']
            processed_data = self.process_numeric_fields(data, numeric_fields)

            new_record = Attachment(**processed_data)
            db.session.add(new_record)
            db.session.commit()

            result = {'id': new_record.id, 'message': 'attachments新增成功'}
            print(f"【{Attachment.__tablename__}创建成功】ID: {new_record.id}")
            return result
        except Exception as e:
            db.session.rollback()
            raise Exception(f'创建附件失败：{str(e)}')

    def get_attachment_list(self, page: int = 1, size: int = 10,
                           filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取附件列表"""
        try:
            query = Attachment.query

            # 附件筛选
            if filters:
                if 'uploader_account' in filters:
                    query = query.filter(Attachment.uploader_account == filters['uploader_account'])
                if 'usage_type' in filters:
                    query = query.filter(Attachment.usage_type == filters['usage_type'])

            return self.get_paginated_list(page, size, None, 'id')
        except Exception as e:
            raise Exception(f'查询附件列表失败：{str(e)}')