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
# 管理员数据增删改查接口（修复旧头像删除）
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

        # 新增操作（保持不变）
        if operate_type == 'add':
            required_fields = ['account', 'username', 'phone', 'password']
            for field in required_fields:
                if field not in kwargs or not str(kwargs[field]).strip():
                    return jsonify({'success': False, 'message': f'缺少必填字段：{field}', 'data': None}), 400

            password = kwargs.pop('password')
            new_record = model(** kwargs)
            new_record.set_password(password)
            db.session.add(new_record)
            db.session.commit()

            result = {
                'id': new_record.id,
                'table_name': table_name,
                'message': '用户创建成功，请上传头像'
            }
            print(f"【用户创建成功】{table_name} ID: {new_record.id}")

        # 删除操作（保持不变）
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

        # 核心修复：edit/update 时删除旧头像
        elif operate_type in ['update', 'edit']:
            record_id = data.get('id')
            update_kwargs = data.get('kwargs', {})

            if not record_id:
                return jsonify({'success': False, 'message': '缺少更新条件：id', 'data': None}), 400
            if not update_kwargs:
                return jsonify({'success': False, 'message': '缺少更新内容：kwargs', 'data': None}), 400

            query_kwargs = {'id': int(record_id)}
            old_record = model.query.filter_by(**query_kwargs).first()  # 查询旧记录

            # 修复点1：如果更新了avatar（新URL非空），删除旧头像
            if table_name in ['admin_info', 'user_info'] and 'avatar' in update_kwargs:
                new_avatar = update_kwargs['avatar']
                # 情况1：新头像为空 → 删除旧头像（原有逻辑保留）
                if not new_avatar or new_avatar.strip() == '':
                    if old_record and old_record.avatar:
                        filename = old_record.avatar.split('/')[-1]
                        LocalImageStorage().delete_image(filename)
                        print(f"【更新为空】删除旧头像：{filename}")
                # 情况2：新头像不为空 → 先删旧头像，再保存新头像
                else:
                    if old_record and old_record.avatar:
                        old_filename = old_record.avatar.split('/')[-1]
                        LocalImageStorage().delete_image(old_filename)
                        print(f"【更新新头像】删除旧头像：{old_filename}")

            updated_count = model.query.filter_by(** query_kwargs).update(update_kwargs)
            db.session.commit()
            result = {'updated_count': updated_count, 'message': f'更新{updated_count}条'}

        # 查询操作（保持不变）
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
        return jsonify({'success': False, 'message': f'操作失败：{str(e)}', 'data': None}), 500
