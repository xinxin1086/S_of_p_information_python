import os
import jwt
from datetime import datetime, timedelta
from flask import request, jsonify
from config import Config
from components import db, token_required, LocalImageStorage  # 引用公共组件
from components.models import Admin, User  # 引用公共模型
from admin import admin_bp  # 导入当前模块蓝图


# 管理员登录接口（无需前缀，单独注册在/admin/login）
@admin_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        account = data.get('account')
        password = data.get('password')
        print(f"【接收登录数据】account: {account}, password: {password[:3]}***")

        if not account or not password:
            print("【登录失败】账号或密码为空")
            return jsonify({
                'success': False,
                'message': '账号和密码不能为空',
                'data': None
            }), 400

        user = Admin.query.filter_by(account=account).first()
        if not user or not user.check_password(password):
            print(f"【登录失败】账号或密码错误，account: {account}")
            return jsonify({
                'success': False,
                'message': '账号或密码错误',
                'data': None
            }), 401

        # 生成JWT令牌
        token = jwt.encode({
            'user_id': user.id,
            'account': user.account,
            'exp': datetime.utcnow() + timedelta(seconds=Config.JWT_EXPIRATION_DELTA)
        }, Config.JWT_SECRET_KEY, algorithm='HS256')

        response_data = {
            'success': True,
            'message': '登录成功',
            'data': {
                'token': token,
                'user': {'id': user.id, 'account': user.account},
                'status': 'success'
            }
        }
        print(f"【传出登录响应】{response_data}")
        return jsonify(response_data), 200
    except Exception as e:
        print(f"【登录异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'登录失败：{str(e)}',
            'data': None
        }), 500

# 管理员信息查询接口（需登录）
@admin_bp.route('/list', methods=['GET'])
@token_required
def get_admin_list(current_user):
    try:
        print(f"【接收查询请求】当前用户: {current_user.account}")
        admins = Admin.query.all()
        data_list = []
        for admin in admins:
            item = {
                'id': admin.id,
                'account': admin.account,
                'username': admin.username,
                'phone': admin.phone or '无',
                'email': admin.email or '无',
                'avatar': admin.avatar or '无',
                'role': admin.role or '普通用户'
            }
            data_list.append(item)
            print(f"【管理员数据】{item}")

        response_data = {
            'success': True,
            'message': '查询成功' if data_list else '无数据',
            'data': {
                'fields': Admin.get_fields_info(),
                'items': data_list
            }
        }
        print(f"【传出查询响应】{response_data}")
        return jsonify(response_data), 200
    except Exception as e:
        print(f"【查询异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


# 管理员数据增删改查接口（通用操作）
# 管理员数据增删改查接口（仅处理用户创建，不含图片）
@admin_bp.route('/operate', methods=['POST'])
@token_required
def db_operate(current_user):
    try:
        data = request.get_json()
        print(f"【接收操作请求】用户: {current_user.account}, 参数: {data}")

        required = ['table_name', 'operate_type']
        for param in required:
            if param not in data:
                return jsonify({'success': False, 'message': f'缺少参数：{param}', 'data': None}), 400

        table_name = data['table_name']
        operate_type = data['operate_type'].lower()
        kwargs = data.get('kwargs', {})
        supported_tables = {'admin_info': Admin, 'user_info': User}

        if table_name not in supported_tables:
            return jsonify({'success': False, 'message': f'不支持表：{table_name}', 'data': None}), 400
        model = supported_tables[table_name]
        result = None

        # 新增操作（仅处理用户信息，无图片逻辑）
        if operate_type == 'add':
            # 校验必填字段
            required_fields = ['account', 'username', 'phone', 'password']
            for field in required_fields:
                if field not in kwargs or not str(kwargs[field]).strip():
                    return jsonify({'success': False, 'message': f'缺少必填字段：{field}', 'data': None}), 400

            password = kwargs.pop('password')
            new_record = model(** kwargs)
            new_record.set_password(password)  # 密码加密
            db.session.add(new_record)
            db.session.commit()

            # 关键：返回创建成功的记录ID，供前端上传图片时使用
            result = {
                'id': new_record.id,  # 记录ID（核心参数）
                'table_name': table_name,  # 表名（区分admin/user）
                'message': '用户创建成功，请上传头像'
            }
            print(f"【用户创建成功】{table_name} ID: {new_record.id}")

        # 其余删除、更新、查询逻辑保持不变...
        elif operate_type == 'delete':
            records = model.query.filter_by(**kwargs).all()
            if records and table_name in ['admin_info', 'user_info']:
                image_storage = LocalImageStorage()
                for record in records:
                    if record.avatar:
                        filename = record.avatar.split('/')[-1]
                        image_storage.delete_image(filename)
                        print(f"【删除关联头像】文件名: {filename}")
            deleted_count = model.query.filter_by(**kwargs).delete()
            db.session.commit()
            result = {'deleted_count': deleted_count, 'message': f'删除{deleted_count}条'}

        elif operate_type == 'update':
            query_kwargs = data.get('query_kwargs', {})
            update_kwargs = data.get('update_kwargs', {})
            if table_name in ['admin_info', 'user_info'] and 'avatar' in update_kwargs:
                new_avatar = update_kwargs['avatar']
                if not new_avatar or new_avatar.strip() == '':
                    old_record = model.query.filter_by(**query_kwargs).first()
                    if old_record and old_record.avatar:
                        filename = old_record.avatar.split('/')[-1]
                        image_storage = LocalImageStorage()
                        image_storage.delete_image(filename)
            updated_count = model.query.filter_by(** query_kwargs).update(update_kwargs)
            db.session.commit()
            result = {'updated_count': updated_count, 'message': f'更新{updated_count}条'}

        elif operate_type == 'query':
            page = data.get('page', 1)
            size = data.get('size', 10)
            pagination = model.query.filter_by(**kwargs).paginate(page=page, per_page=size)
            items = [{col.name: getattr(item, col.name) for col in item.__table__.columns} for item in pagination.items]
            result = {'total': pagination.total, 'page': page, 'items': items}

        else:
            return jsonify({'success': False, 'message': '操作类型错误', 'data': None}), 400

        return jsonify({'success': True, 'message': '操作成功', 'data': result}), 200

    except Exception as e:
        db.session.rollback()
        print(f"【操作异常】{str(e)}")
        # 关键：用户创建失败时，返回明确错误，前端放弃传图
        return jsonify({'success': False, 'message': f'用户创建失败：{str(e)}', 'data': None}), 500

#
# @admin_bp.route('/operate', methods=['POST'])
# @token_required
# def db_operate(current_user):
#     try:
#         data = request.get_json()
#         print(f"【接收操作请求】用户: {current_user.account}, 参数: {data}")
#
#         required = ['table_name', 'operate_type']
#         for param in required:
#             if param not in data:
#                 return jsonify({'success': False, 'message': f'缺少参数：{param}', 'data': None}), 400
#
#         table_name = data['table_name']
#         operate_type = data['operate_type'].lower()
#         kwargs = data.get('kwargs', {})
#         # 定义支持的表
#         supported_tables = {
#             'admin_info': Admin,
#             'user_info': User
#         }
#
#         if table_name not in supported_tables:
#             return jsonify({'success': False, 'message': f'不支持表：{table_name}', 'data': None}), 400
#         model = supported_tables[table_name]
#         result = None
#
#         # 正常接收avatar URL并存储（前端需先调用公共上传接口获取URL）
#         if operate_type == 'add':
#             password = kwargs.pop('password', None)
#             new_record = model(**kwargs)
#             # 强制校验：只要是管理员/用户表且有密码，必须加密
#             print(f"【新增记录】{new_record}")
#             if (table_name in ['admin_info', 'user_info']) and password:
#                 new_record.set_password(password)  # 确保加密逻辑执行
#             db.session.add(new_record)
#             db.session.commit()
#             result = {'id': new_record.id, 'message': '新增成功'}
#
#         # 删除：若删除整条记录，同步删除关联的头像图片
#         elif operate_type == 'delete':
#             # 先查询要删除的记录，获取avatar URL
#             records = model.query.filter_by(**kwargs).all()
#             if records and table_name == ['admin_info', 'user_info']:
#                 # 遍历记录，删除关联的本地图片
#                 image_storage = LocalImageStorage()
#                 for record in records:
#                     if record.avatar:
#                         # 从URL中提取文件名
#                         filename = record.avatar.split('/')[-1]
#                         image_storage.delete_image(filename)
#                         print(f"【删除关联头像】文件名: {filename}")
#             # 执行数据库删除
#             deleted_count = model.query.filter_by(**kwargs).delete()
#             db.session.commit()
#             result = {'deleted_count': deleted_count, 'message': f'删除{deleted_count}条'}
#
#         # 更新：若更新avatar为null/空，同步删除原本地图片
#         elif operate_type == 'update':
#             query_kwargs = data.get('query_kwargs', {})
#             update_kwargs = data.get('update_kwargs', {})
#
#             # 检查是否需要删除原头像（update_kwargs中avatar为null/空字符串）
#             if table_name == ['admin_info', 'user_info'] and 'avatar' in update_kwargs:
#                 new_avatar = update_kwargs['avatar']
#                 # 当新头像为null/空时，删除原头像图片
#                 if not new_avatar or new_avatar.strip() == '':
#                     # 查询原记录的avatar URL
#                     old_record = model.query.filter_by(**query_kwargs).first()
#                     if old_record and old_record.avatar:
#                         # 提取文件名并删除本地图片
#                         filename = old_record.avatar.split('/')[-1]
#                         image_storage = LocalImageStorage()
#                         image_storage.delete_image(filename)
#                         print(f"【更新时删除原头像】文件名: {filename}")
#
#             # 执行数据库更新（新avatar URL直接存储）
#             updated_count = model.query.filter_by(** query_kwargs).update(update_kwargs)
#             db.session.commit()
#             result = {'updated_count': updated_count, 'message': f'更新{updated_count}条'}
#
#         # 查询：正常返回avatar URL
#         elif operate_type == 'query':
#             page = data.get('page', 1)
#             size = data.get('size', 10)
#             pagination = model.query.filter_by(**kwargs).paginate(page=page, per_page=size)
#             items = [{col.name: getattr(item, col.name) for col in item.__table__.columns} for item in pagination.items]
#             result = {'total': pagination.total, 'page': page, 'items': items}
#
#         else:
#             return jsonify({'success': False, 'message': '操作类型错误', 'data': None}), 400
#
#         print(f"【操作结果】{result}")
#         return jsonify({'success': True, 'message': '操作成功', 'data': result}), 200
#
#     except Exception as e:
#         db.session.rollback()
#         print(f"【传出查询响应】{current_user}")
#         print(f"原始数据：{request.data}")
#         print(f"【操作异常】{str(e)}")
#         return jsonify({'success': False, 'message': f'操作失败：{str(e)}', 'data': None}), 500
