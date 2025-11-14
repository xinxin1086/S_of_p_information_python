import jwt
from datetime import datetime, timedelta
from flask import request, jsonify
from config import Config
from components import db, token_required  # 引用公共组件
from components.models import Admin  # 引用公共模型
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
@admin_bp.route('/operate', methods=['POST'])
@token_required
def db_operate(current_user):
    try:
        data = request.get_json()
        print(f"【接收操作请求】用户: {current_user.account}, 参数: {data}")

        # 校验参数
        required = ['table_name', 'operate_type']
        for param in required:
            if param not in data:
                return jsonify({'success': False, 'message': f'缺少参数：{param}', 'data': None}), 400

        table_name = data['table_name']
        operate_type = data['operate_type'].lower()
        kwargs = data.get('kwargs', {})

        # 支持的表（仅管理员可操作）
        supported_tables = {'admin_info': Admin}
        if table_name not in supported_tables:
            return jsonify({'success': False, 'message': f'不支持表：{table_name}', 'data': None}), 400
        model = supported_tables[table_name]
        result = None

        # 新增
        if operate_type == 'add':
            # 先从kwargs中移除password，再创建实例
            password = kwargs.pop('password', None)  # 取出密码并删除原参数
            new_record = model(**kwargs)  # 此时kwargs中已无password，不会触发无效参数错误
            if table_name == 'admin_info' and password:  # 有密码则加密
                new_record.set_password(password)
            db.session.add(new_record)
            db.session.commit()
            result = {'id': new_record.id, 'message': '新增成功'}

        # 删除
        elif operate_type == 'delete':
            deleted_count = model.query.filter_by(**kwargs).delete()
            db.session.commit()
            result = {'deleted_count': deleted_count, 'message': f'删除{deleted_count}条'}

        # 更新
        elif operate_type == 'update':
            query_kwargs = data.get('query_kwargs', {})
            update_kwargs = data.get('update_kwargs', {})
            updated_count = model.query.filter_by(** query_kwargs).update(update_kwargs)
            db.session.commit()
            result = {'updated_count': updated_count, 'message': f'更新{updated_count}条'}

        # 查询
        elif operate_type == 'query':
            page = data.get('page', 1)
            size = data.get('size', 10)
            pagination = model.query.filter_by(**kwargs).paginate(page=page, per_page=size)
            items = [{col.name: getattr(item, col.name) for col in item.__table__.columns} for item in pagination.items]
            result = {'total': pagination.total, 'page': page, 'items': items}

        else:
            return jsonify({'success': False, 'message': '操作类型错误', 'data': None}), 400

        print(f"【操作结果】{result}")
        return jsonify({'success': True, 'message': '操作成功', 'data': result}), 200

    except Exception as e:
        db.session.rollback()
        print(f"【传出查询响应】{current_user}")
        # print(f"原始数据：{request.data}")
        print(f"【操作异常】{str(e)}")
        return jsonify({'success': False, 'message': f'操作失败：{str(e)}', 'data': None}), 500