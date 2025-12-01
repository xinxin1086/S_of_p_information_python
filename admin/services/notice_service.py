# admin/services/notice_service.py
# 公告管理服务类

from datetime import datetime
from typing import Dict, Any, Optional
from components import db
from components.models import Notice
from .base_service import BaseService


class NoticeService(BaseService):
    """公告管理服务类"""

    def __init__(self):
        super().__init__(Notice)

    def create_notice(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建公告"""
        # 验证必填字段
        required_fields = ['release_title', 'release_notice', 'notice_type']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                raise Exception(f'缺少必填字段：{field}')

        # 发布时间自动设置为当前时间（不可变更）
        release_time = datetime.now()
        expiration = data.get('expiration')

        # 过滤掉 Notice 模型中不存在的字段（如 status）
        valid_kwargs = {
            'release_title': data['release_title'],
            'release_notice': data['release_notice'],
            'notice_type': data['notice_type']
        }

        try:
            new_record = Notice(
                release_time=release_time,
                update_time=datetime.now(),  # 初始更新时间=发布时间
                expiration=self.parse_datetime(expiration) if expiration else None,
                **valid_kwargs
            )
            db.session.add(new_record)
            db.session.commit()

            result = {
                'id': new_record.id,
                'message': '公告新增成功'
            }
            print(f"【公告创建成功】ID: {new_record.id}, 发布时间: {new_record.release_time.isoformat()}")
            return result
        except Exception as e:
            db.session.rollback()
            raise Exception(f'创建公告失败：{str(e)}')

    def update_notice(self, query_type: str = 'edit', **kwargs) -> Dict[str, Any]:
        """更新公告"""
        try:
            if query_type == 'edit':
                update_kwargs = kwargs.get('data', {}).copy()
                notice_id = kwargs.get('id')
                if not notice_id:
                    raise Exception('公告更新缺少主键：id')
                query_kwargs = {'id': int(notice_id)}

                # 禁止修改发布时间
                update_kwargs.pop('release_time', None)

                # 处理到期时间
                if 'expiration' in update_kwargs:
                    update_kwargs['expiration'] = self.parse_datetime(update_kwargs['expiration']) if update_kwargs['expiration'] else None

                update_kwargs.pop('id', None)
            else:
                query_kwargs = kwargs.get('query_kwargs', {})
                update_kwargs = kwargs.get('update_kwargs', {})
                # 禁止修改发布时间
                update_kwargs.pop('release_time', None)
                # 处理时间字段
                if 'expiration' in update_kwargs:
                    update_kwargs['expiration'] = self.parse_datetime(update_kwargs['expiration']) if update_kwargs['expiration'] else None

            # 校验参数
            if not query_kwargs or not update_kwargs:
                raise Exception('需同时提供查询条件和更新内容')

            return self.update_record(query_kwargs, update_kwargs)
        except Exception as e:
            if '未找到' in str(e):
                print(f"【公告更新失败】{str(e)}")
                raise Exception('未找到待更新的公告')
            raise Exception(f'更新公告失败：{str(e)}')

    def delete_notice(self, query_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """删除公告"""
        delete_kwargs = query_kwargs.copy()

        # 支持按 id 或 release_time 删除（id 优先）
        if 'id' in delete_kwargs:
            delete_kwargs['id'] = int(delete_kwargs['id'])
        # 处理 release_time 条件
        if 'release_time' in delete_kwargs:
            delete_kwargs['release_time'] = self.parse_datetime(delete_kwargs['release_time'])

        result = self.delete_record(delete_kwargs)
        print(f"【公告删除成功】条件：{delete_kwargs}，删除条数：{result['deleted_count']}")
        return result

    def get_notice_list(self, page: int = 1, size: int = 10,
                       filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取公告列表（支持多条件筛选）"""
        try:
            query = Notice.query

            # 公告多条件筛选
            if filters:
                if 'title' in filters:
                    query = query.filter(Notice.release_title.like(f"%{filters['title']}%"))
                if 'notice_type' in filters:
                    query = query.filter(Notice.notice_type == filters['notice_type'])
                if 'expiration_start' in filters:
                    start_time = self.parse_datetime(filters['expiration_start'])
                    if start_time:
                        query = query.filter(Notice.expiration >= start_time)
                if 'release_time_start' in filters:
                    start_time = self.parse_datetime(filters['release_time_start'])
                    if start_time:
                        query = query.filter(Notice.release_time >= start_time)
                if 'release_time_end' in filters:
                    end_time = self.parse_datetime(filters['release_time_end'])
                    if end_time:
                        query = query.filter(Notice.release_time <= end_time)

            pagination = query.order_by(Notice.release_time.desc()).paginate(page=page, per_page=size)
            notices = pagination.items
            total = pagination.total

            result_list = []
            for notice in notices:
                result_list.append({
                    'id': notice.id,
                    'release_time': self.format_datetime(notice.release_time),
                    'update_time': self.format_datetime(notice.update_time),
                    'release_title': notice.release_title,
                    'release_notice': notice.release_notice,
                    'expiration': self.format_datetime(notice.expiration) if notice.expiration else None,
                    'notice_type': notice.notice_type
                })

            return {
                'total': total,
                'page': page,
                'size': size,
                'items': result_list,
                'message': '公告列表查询成功'
            }
        except Exception as e:
            raise Exception(f'查询公告列表失败：{str(e)}')

    def get_notice_detail(self, notice_id: int) -> Dict[str, Any]:
        """获取公告详情"""
        return self.get_record_by_id(notice_id)