# admin/services/content_service.py
# 内容管理服务类（科普文章、活动等）

from typing import Dict, Any
from components import db
from components.models import ScienceArticle, Activity
from .base_service import BaseService, TimeFieldMixin


class ScienceArticleService(BaseService, TimeFieldMixin):
    """科普文章管理服务类"""

    def __init__(self):
        super().__init__(ScienceArticle)

    def create_article(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建科普文章"""
        # 验证必填字段
        required_fields = ['title', 'content', 'author_account']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                raise Exception(f'缺少必填字段：{field}')

        try:
            new_record = ScienceArticle(
                title=data['title'],
                content=data['content'],
                author_account=data['author_account'],
                cover_image=data.get('cover_image'),
                status=data.get('status', 'draft'),
                published_at=self.parse_datetime(data.get('published_at')) if data.get('published_at') else None
            )
            db.session.add(new_record)
            db.session.commit()

            result = {'id': new_record.id, 'message': '科普文章新增成功'}
            print(f"【科普文章创建成功】ID: {new_record.id}")
            return result
        except Exception as e:
            db.session.rollback()
            raise Exception(f'创建科普文章失败：{str(e)}')

    def update_article(self, query_type: str = 'edit', **kwargs) -> Dict[str, Any]:
        """更新科普文章"""
        if query_type == 'edit':
            update_kwargs = kwargs.get('data', {}).copy()
            record_id = kwargs.get('id')
            if not record_id:
                raise Exception('科普文章更新缺少主键：id')
            query_kwargs = {'id': int(record_id)}
            update_kwargs.pop('id', None)
        else:
            query_kwargs = kwargs.get('query_kwargs', {})
            update_kwargs = kwargs.get('update_kwargs', {})

        # 处理时间字段
        time_fields = ['published_at']
        update_kwargs = self.process_time_fields(update_kwargs, time_fields)

        return self.update_record(query_kwargs, update_kwargs)

    def get_article_list(self, page: int = 1, size: int = 10,
                        filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取科普文章列表"""
        try:
            query = ScienceArticle.query

            # 科普文章筛选
            if filters:
                if 'author_account' in filters:
                    query = query.filter(ScienceArticle.author_account == filters['author_account'])
                if 'status' in filters:
                    query = query.filter(ScienceArticle.status == filters['status'])
                if 'title' in filters:
                    query = query.filter(ScienceArticle.title.like(f"%{filters['title']}%"))

            return self.get_paginated_list(page, size, None, 'id')
        except Exception as e:
            raise Exception(f'查询科普文章列表失败：{str(e)}')


class ActivityService(BaseService, TimeFieldMixin):
    """活动管理服务类"""

    def __init__(self):
        super().__init__(Activity)

    def create_activity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建活动"""
        # 验证必填字段
        required_fields = ['title', 'description', 'organizer_account', 'start_time', 'end_time']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                raise Exception(f'缺少必填字段：{field}')

        try:
            # 处理时间字段
            time_fields = ['start_time', 'end_time']
            processed_data = self.process_time_fields(data, time_fields)

            new_record = Activity(
                title=processed_data['title'],
                description=processed_data['description'],
                organizer_account=processed_data['organizer_account'],
                location=processed_data.get('location'),
                start_time=processed_data['start_time'],
                end_time=processed_data['end_time'],
                max_participants=processed_data.get('max_participants'),
                status=processed_data.get('status', 'draft')
            )
            db.session.add(new_record)
            db.session.commit()

            result = {'id': new_record.id, 'message': '活动新增成功'}
            print(f"【活动创建成功】ID: {new_record.id}")
            return result
        except Exception as e:
            db.session.rollback()
            raise Exception(f'创建活动失败：{str(e)}')

    def update_activity(self, query_type: str = 'edit', **kwargs) -> Dict[str, Any]:
        """更新活动"""
        if query_type == 'edit':
            update_kwargs = kwargs.get('data', {}).copy()
            record_id = kwargs.get('id')
            if not record_id:
                raise Exception('活动更新缺少主键：id')
            query_kwargs = {'id': int(record_id)}
            update_kwargs.pop('id', None)
        else:
            query_kwargs = kwargs.get('query_kwargs', {})
            update_kwargs = kwargs.get('update_kwargs', {})

        # 处理时间字段
        time_fields = ['start_time', 'end_time']
        update_kwargs = self.process_time_fields(update_kwargs, time_fields)

        # 处理数字字段
        numeric_fields = ['max_participants']
        update_kwargs = self.process_numeric_fields(update_kwargs, numeric_fields)

        return self.update_record(query_kwargs, update_kwargs)

    def delete_activity(self, query_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """删除活动"""
        # 处理数字字段
        numeric_fields = ['id', 'activity_id']
        processed_kwargs = self.process_numeric_fields(query_kwargs, numeric_fields)

        # 处理时间字段
        time_fields = ['start_time', 'end_time']
        processed_kwargs = self.process_time_fields(processed_kwargs, time_fields)

        return self.delete_record(processed_kwargs)

    def get_activity_list(self, page: int = 1, size: int = 10,
                         filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取活动列表"""
        try:
            query = Activity.query

            # 活动筛选
            if filters:
                if 'organizer_account' in filters:
                    query = query.filter(Activity.organizer_account == filters['organizer_account'])
                if 'status' in filters:
                    query = query.filter(Activity.status == filters['status'])
                if 'title' in filters:
                    query = query.filter(Activity.title.like(f"%{filters['title']}%"))

            return self.get_paginated_list(page, size, None, 'id')
        except Exception as e:
            raise Exception(f'查询活动列表失败：{str(e)}')