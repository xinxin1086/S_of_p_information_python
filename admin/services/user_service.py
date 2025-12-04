# admin/services/user_service.py
# 用户管理服务类

from typing import Dict, Any
from components import db
from components.models import Admin, User, DeletedUser
from .base_service import BaseService, UserServiceMixin


class AdminService(BaseService, UserServiceMixin):
    """管理员管理服务类"""

    def __init__(self):
        super().__init__(Admin)

    def create_admin(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建管理员"""
        # 验证必填字段
        required_fields = ['account', 'username', 'phone', 'password']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                raise Exception(f'缺少必填字段：{field}')

        # 处理密码
        password = data.pop('password')

        # 创建管理员记录
        try:
            new_record = Admin(**data)
            new_record.set_password(password)
            db.session.add(new_record)
            db.session.commit()

            result = {
                'id': new_record.id,
                'table_name': 'admin_info',
                'message': '管理员创建成功，请上传头像'
            }
            print(f"【管理员创建成功】ID: {new_record.id}")
            return result
        except Exception as e:
            db.session.rollback()
            raise Exception(f'创建管理员失败：{str(e)}')

    def update_admin(self, record_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新管理员"""
        query_kwargs = {'id': record_id}
        old_record = self.model_class.query.filter_by(**query_kwargs).first()
        if not old_record:
            raise Exception(f'未找到ID为{record_id}的管理员记录')

        # 处理密码更新
        if 'password' in update_data:
            new_password = update_data.pop('password')
            if new_password and new_password.strip():
                old_record.set_password(new_password)
                print(f"【更新密码】管理员ID: {record_id} 的密码已更新")

        # 处理头像更新
        if 'avatar' in update_data:
            self.handle_avatar_update(old_record, update_data.get('avatar'))

        return self.update_record(query_kwargs, update_data)

    def delete_admin(self, query_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """删除管理员"""
        # 先获取要删除的记录，用于处理头像删除
        records = self.model_class.query.filter_by(**query_kwargs).all()

        # 删除关联的头像文件
        self.delete_user_avatar(records)

        return self.delete_record(query_kwargs)

    def get_admin_list(self, page: int = 1, size: int = 10,
                      filter_kwargs: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取管理员列表"""
        result = self.get_paginated_list(page, size, filter_kwargs)

        # 格式化返回数据，只返回需要的字段
        formatted_items = []
        for item in result['items']:
            formatted_items.append({
                'id': item['id'],
                'account': item['account'],
                'username': item['username'],
                'phone': item.get('phone', '无'),
                'email': item.get('email', '无'),
                'avatar': item.get('avatar', '无'),
                'role': item.get('role', '普通用户')
            })

        result['items'] = formatted_items
        result['message'] = '管理员列表查询成功'
        return result


class UserService(BaseService, UserServiceMixin):
    """普通用户管理服务类"""

    def __init__(self):
        super().__init__(User)

    def create_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建用户"""
        # 验证必填字段（移除username，因为新模型没有此字段）
        required_fields = ['account', 'phone', 'password']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                raise Exception(f'缺少必填字段：{field}')

        # 检查账号和手机号是否已被使用（仅检查未注销用户）
        existing_user = User.query.filter_by(
            account=data['account'], is_deleted=0
        ).first()
        if existing_user:
            raise Exception(f'账号 {data["account"]} 已被使用')

        existing_phone = User.query.filter_by(
            phone=data['phone'], is_deleted=0
        ).first()
        if existing_phone:
            raise Exception(f'手机号 {data["phone"]} 已被使用')

        # 处理密码
        password = data.pop('password')

        # 创建用户记录
        try:
            new_record = User(**data)
            new_record.set_password(password)
            db.session.add(new_record)
            db.session.commit()

            result = {
                'id': new_record.id,
                'table_name': 'user_info',
                'message': '用户创建成功'
            }
            print(f"【用户创建成功】ID: {new_record.id}")
            return result
        except Exception as e:
            db.session.rollback()
            raise Exception(f'创建用户失败：{str(e)}')

    def update_user(self, record_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新用户"""
        query_kwargs = {'id': record_id}
        old_record = self.model_class.query.filter_by(**query_kwargs).first()
        if not old_record:
            raise Exception(f'未找到ID为{record_id}的用户记录')

        # 处理密码更新
        if 'password' in update_data:
            new_password = update_data.pop('password')
            if new_password and new_password.strip():
                old_record.set_password(new_password)
                print(f"【更新密码】用户ID: {record_id} 的密码已更新")

        # 处理头像更新
        if 'avatar' in update_data:
            self.handle_avatar_update(old_record, update_data.get('avatar'))

        return self.update_record(query_kwargs, update_data)

    def delete_user(self, query_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """删除用户（软删除）"""
        # 获取要删除的用户记录
        users = self.model_class.query.filter_by(**query_kwargs).all()
        if not users:
            raise Exception('未找到要删除的用户记录')

        deleted_count = 0
        deleted_user_records = []

        for user in users:
            if user.is_deleted == 1:
                continue  # 跳过已删除的用户

            # 执行软删除
            deleted_user_record, message = user.soft_delete()
            if deleted_user_record:
                deleted_user_records.append(deleted_user_record)
                db.session.add(deleted_user_record)
            deleted_count += 1
            print(f"【用户软删除】用户ID: {user.id}, 账号: {user.account}")

        try:
            db.session.commit()
            result = {
                'deleted_count': deleted_count,
                'deleted_user_records': len(deleted_user_records),
                'message': f'成功软删除 {deleted_count} 个用户'
            }
            return result
        except Exception as e:
            db.session.rollback()
            raise Exception(f'用户删除失败：{str(e)}')

    def get_deleted_users(self, page: int = 1, size: int = 10) -> Dict[str, Any]:
        """获取已注销用户列表"""
        try:
            query = DeletedUser.query.order_by(DeletedUser.delete_time.desc())
            paginated_query = query.paginate(page=page, per_page=size, error_out=False)

            items = []
            for deleted_user in paginated_query.items:
                items.append({
                    'id': deleted_user.id,
                    'original_user_id': deleted_user.original_user_id,
                    'original_account': deleted_user.original_account,
                    'original_phone': deleted_user.original_phone or '无',
                    'delete_time': deleted_user.delete_time.strftime('%Y-%m-%d %H:%M:%S') if deleted_user.delete_time else '无'
                })

            return {
                'items': items,
                'total': paginated_query.total,
                'page': page,
                'size': size,
                'pages': paginated_query.pages,
                'message': '已注销用户列表查询成功'
            }
        except Exception as e:
            raise Exception(f'查询已注销用户失败：{str(e)}')

    def get_user_list(self, page: int = 1, size: int = 10,
                     filter_kwargs: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取用户列表（仅显示未注销用户）"""
        # 添加默认过滤条件：只显示未注销用户
        if filter_kwargs is None:
            filter_kwargs = {}
        filter_kwargs['is_deleted'] = 0

        result = self.get_paginated_list(page, size, filter_kwargs)

        # 格式化返回数据，适应新的字段结构
        formatted_items = []
        for item in result['items']:
            formatted_items.append({
                'id': item['id'],
                'account': item['account'],
                'phone': item.get('phone', '无'),
                'is_deleted': item.get('is_deleted', 0),
                'status': '正常' if item.get('is_deleted', 0) == 0 else '已注销'
            })

        result['items'] = formatted_items
        result['message'] = '用户列表查询成功'
        return result