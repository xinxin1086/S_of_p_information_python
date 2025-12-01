# admin/services/base_service.py
# 通用CRUD服务基类

from datetime import datetime
from typing import Dict, Any, List, Optional
from components import db, LocalImageStorage


class BaseService:
    """通用CRUD服务基类，提供基础的数据操作方法"""

    def __init__(self, model_class):
        self.model_class = model_class

    @staticmethod
    def parse_datetime(time_str: str) -> Optional[datetime]:
        """解析时间字符串为datetime对象"""
        if not time_str:
            return None
        try:
            time_str = time_str.replace('Z', '+00:00')
            if '.' in time_str:
                parts = time_str.split('.')
                microsec = parts[1].split('+')[0].ljust(6, '0')[:6]
                time_str = f"{parts[0]}.{microsec}+{parts[1].split('+')[1]}"
            return datetime.fromisoformat(time_str)
        except Exception as e:
            print(f"【时间解析失败】{time_str} -> {str(e)}")
            return None

    @staticmethod
    def format_datetime(dt: datetime) -> str:
        """格式化datetime对象为ISO字符串"""
        if dt and hasattr(dt, 'isoformat'):
            return dt.isoformat().replace('+00:00', 'Z')
        return str(dt) if dt else None

    def format_model_data(self, model_instance) -> Dict[str, Any]:
        """格式化模型实例数据为字典"""
        item_data = {}
        for column in model_instance.__table__.columns:
            value = getattr(model_instance, column.name)
            if value is not None:
                # 处理时间字段
                if column.type.__class__.__name__ in ['DateTime', 'TIMESTAMP']:
                    item_data[column.name] = self.format_datetime(value)
                else:
                    item_data[column.name] = value
            else:
                item_data[column.name] = None
        return item_data

    def create_record(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建记录"""
        try:
            new_record = self.model_class(**data)
            db.session.add(new_record)
            db.session.commit()
            return {
                'id': new_record.id,
                'message': f'{self.model_class.__tablename__}新增成功'
            }
        except Exception as e:
            db.session.rollback()
            raise Exception(f'创建{self.model_class.__tablename__}记录失败：{str(e)}')

    def get_record_by_id(self, record_id: int) -> Dict[str, Any]:
        """根据ID获取记录详情"""
        record = self.model_class.query.filter_by(id=record_id).first()
        if not record:
            raise Exception(f'未找到ID为{record_id}的记录')

        return {
            'item': self.format_model_data(record),
            'message': f'{self.model_class.__tablename__}详情查询成功'
        }

    def update_record(self, query_kwargs: Dict[str, Any], update_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """更新记录"""
        try:
            # 检查记录是否存在
            existing_record = self.model_class.query.filter_by(**query_kwargs).first()
            if not existing_record:
                raise Exception(f'未找到符合条件的记录')

            updated_count = self.model_class.query.filter_by(**query_kwargs).update(update_kwargs)
            db.session.commit()
            return {
                'updated_count': updated_count,
                'message': f'更新{updated_count}条{self.model_class.__tablename__}记录'
            }
        except Exception as e:
            db.session.rollback()
            raise Exception(f'更新{self.model_class.__tablename__}记录失败：{str(e)}')

    def delete_record(self, query_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """删除记录"""
        try:
            deleted_count = self.model_class.query.filter_by(**query_kwargs).delete()
            db.session.commit()
            return {
                'deleted_count': deleted_count,
                'message': f'删除{deleted_count}条{self.model_class.__tablename__}记录'
            }
        except Exception as e:
            db.session.rollback()
            raise Exception(f'删除{self.model_class.__tablename__}记录失败：{str(e)}')

    def get_paginated_list(self, page: int = 1, size: int = 10,
                          filter_kwargs: Optional[Dict[str, Any]] = None,
                          order_by_field: str = 'id') -> Dict[str, Any]:
        """获取分页列表"""
        try:
            query = self.model_class.query

            # 应用过滤条件
            if filter_kwargs:
                query = query.filter_by(**filter_kwargs)

            # 分页
            pagination = query.order_by(getattr(self.model_class, order_by_field).desc()).paginate(
                page=page, per_page=size
            )
            items = pagination.items
            total = pagination.total

            # 格式化结果
            result_list = []
            for item in items:
                result_list.append(self.format_model_data(item))

            return {
                'total': total,
                'page': page,
                'size': size,
                'items': result_list,
                'message': f'{self.model_class.__tablename__}列表查询成功'
            }
        except Exception as e:
            raise Exception(f'查询{self.model_class.__tablename__}列表失败：{str(e)}')


class UserServiceMixin:
    """用户服务相关功能混入类"""

    @staticmethod
    def handle_avatar_update(old_record, new_avatar_url: str = None):
        """处理头像更新逻辑"""
        if new_avatar_url == '' or new_avatar_url is None:
            # 新头像为空，删除旧头像
            if old_record.avatar:
                filename = old_record.avatar.split('/')[-1]
                LocalImageStorage().delete_image(filename)
                print(f"【更新为空】删除旧头像：{filename}")
        elif new_avatar_url and old_record.avatar != new_avatar_url:
            # 有新头像且与旧头像不同，删除旧头像
            if old_record.avatar:
                filename = old_record.avatar.split('/')[-1]
                LocalImageStorage().delete_image(filename)
                print(f"【更新新头像】删除旧头像：{filename}")

    @staticmethod
    def delete_user_avatar(users):
        """删除用户头像文件"""
        if users:
            image_storage = LocalImageStorage()
            for user in users:
                if user.avatar:
                    filename = user.avatar.split('/')[-1]
                    image_storage.delete_image(filename)
                    print(f"【删除关联头像】文件名: {filename}")


class TimeFieldMixin:
    """时间字段处理混入类"""

    @staticmethod
    def process_time_fields(data: Dict[str, Any], time_fields: List[str]) -> Dict[str, Any]:
        """处理时间字段"""
        processed_data = data.copy()
        for field in time_fields:
            if field in processed_data:
                processed_data[field] = BaseService.parse_datetime(processed_data[field])
        return processed_data

    @staticmethod
    def process_numeric_fields(data: Dict[str, Any], numeric_fields: List[str]) -> Dict[str, Any]:
        """处理数字字段"""
        processed_data = data.copy()
        for field in numeric_fields:
            if field in processed_data and processed_data[field] is not None:
                try:
                    processed_data[field] = int(processed_data[field])
                except (ValueError, TypeError):
                    pass
        return processed_data