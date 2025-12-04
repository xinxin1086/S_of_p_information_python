#  ./admin/routes.py

import jwt
from datetime import datetime, timedelta
from flask import request, jsonify
from config import Config
from components import db, token_required  # 引用公共组件
from components.models import (
    Admin, ActivityRating
)  # 保留登录和专用接口需要的模型
from admin import admin_bp  # 导入当前模块蓝图
from admin.services.operation_service import OperationService

# 初始化操作服务
operation_service = OperationService()


# 管理员登录接口（无需前缀，单独注册在/admin/login）
@admin_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        account = data.get('account')
        password = data.get('password')
        print(f"【接收登录数据】account: {account}, password: {password}")

        if not account or not password:
            print("【登录失败】账号或密码为空")
            return jsonify({
                'success': False,
                'message': '账号和密码不能为空',
                'data': None
            }), 400

        print(f"【查询管理员】account: {account}")
        user = Admin.query.filter_by(account=account).first()
        print(f"【查询结果】user: {user}, user_id: {user.id if user else None}, username: {user.username if user else None}")

        if not user:
            print(f"【登录失败】未找到账号: {account}")
            return jsonify({
                'success': False,
                'message': '账号不存在',
                'data': None
            }), 401

        print(f"【验证密码】用户ID: {user.id}, 开始密码验证")
        password_valid = user.check_password(password)
        print(f"【验证结果】密码验证结果: {password_valid}")

        if not password_valid:
            print(f"【登录失败】密码错误，account: {account}, user_id: {user.id}")
            return jsonify({
                'success': False,
                'message': '密码错误',
                'data': None
            }), 401

        # 生成JWT令牌
        print(f"【生成令牌】用户ID: {user.id}, 账号: {user.account}, 过期时间: {Config.JWT_EXPIRATION_DELTA}秒")
        token = jwt.encode({
            'user_id': user.id,
            'account': user.account,
            'exp': datetime.utcnow() + timedelta(seconds=Config.JWT_EXPIRATION_DELTA)
        }, Config.JWT_SECRET_KEY, algorithm='HS256')
        print(f"【令牌生成成功】token长度: {len(token)}")

        response_data = {
            'success': True,
            'message': '登录成功',
            'data': {
                'token': token,
                'user': {'id': user.id, 'account': user.account, 'name': user.username, 'role': user.role},
                'status': 'success'
            }
        }
        print(f"【登录成功】用户: {user.account}({user.username}), 角色: {user.role}")
        print(f"【传出登录响应】success: {response_data['success']}, message: {response_data['message']}")
        return jsonify(response_data), 200
    except Exception as e:
        import traceback
        print(f"【登录异常】错误类型: {type(e).__name__}")
        print(f"【登录异常】错误信息: {str(e)}")
        print(f"【登录异常】详细堆栈:")
        for line in traceback.format_exc().split('\n'):
            if line.strip():
                print(f"  {line}")
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


# 管理员数据增删改查接口（新架构 - 使用模块化服务类）
@admin_bp.route('/operate', methods=['POST'])
@token_required
def db_operate(current_user):
    """管理员数据操作主入口函数，使用新的模块化架构"""
    try:
        data = request.get_json()
        print(f"【接收操作请求】用户: {current_user.account}, 参数: {data}")

        # 验证必填参数
        required = ['table_name', 'operate_type']
        for param in required:
            if param not in data:
                return jsonify({
                    'success': False,
                    'message': f'缺少参数：{param}',
                    'data': None
                }), 400

        # 执行操作
        result = operation_service.execute_operation(current_user, data)

        # 添加详细的响应调试信息
        print(f"【操作完成】用户: {current_user.account}")
        print(f"【操作类型】{data.get('operate_type')} {data.get('table_name')}")
        print(f"【响应结果】success: True, message: {result.get('message', '操作成功')}")
        if 'items' in result:
            print(f"【返回数据条数】{len(result.get('items', []))} 条")
        elif 'id' in result:
            print(f"【操作记录ID】{result.get('id')}")
        print(f"【完整响应数据】{result}")

        return jsonify({
            'success': True,
            'message': result.get('message', '操作成功'),
            'data': result
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"【操作异常】用户: {current_user.account}")
        print(f"【异常类型】{type(e).__name__}")
        print(f"【异常信息】{str(e)}")
        print(f"【请求参数】{data}")
        import traceback
        print(f"【异常堆栈】")
        for line in traceback.format_exc().split('\n'):
            if line.strip():
                print(f"  {line}")
        return jsonify({
            'success': False,
            'message': f'操作失败：{str(e)}',
            'data': None
        }), 500


# ============================================================================
# 新增活动评分、讨论和留言管理接口
# ============================================================================

# 活动评分管理接口
@admin_bp.route('/activity-ratings', methods=['GET'])
@token_required
def get_activity_ratings():
    """获取活动评分列表"""
    try:
        # 获取筛选参数
        activity_id = request.args.get('activity_id')
        rater_user_id = request.args.get('rater_user_id')
        score = request.args.get('score')
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))

        query = ActivityRating.query

        # 应用筛选条件
        if activity_id:
            query = query.filter(ActivityRating.activity_id == int(activity_id))
        if rater_user_id:
            query = query.filter(ActivityRating.rater_user_id == int(rater_user_id))
        if score:
            query = query.filter(ActivityRating.score == int(score))

        # 分页查询
        pagination = query.order_by(ActivityRating.create_time.desc()).paginate(page=page, per_page=size)
        ratings = pagination.items
        total = pagination.total

        result_list = []
        for rating in ratings:
            item = {
                'id': rating.id,
                'activity_id': rating.activity_id,
                'rater_user_id': rating.rater_user_id,
                'rater_display': rating.rater_display,
                'score': rating.score,
                'comment_content': rating.comment_content,
                'create_time': rating.create_time.isoformat().replace('+00:00', 'Z'),
                'update_time': rating.update_time.isoformat().replace('+00:00', 'Z')
            }
            result_list.append(item)

        return jsonify({
            'success': True,
            'message': '活动评分列表查询成功',
            'data': {
                'total': total,
                'page': page,
                'size': size,
                'items': result_list
            }
        }), 200

    except Exception as e:
        print(f"【活动评分查询异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


@admin_bp.route('/activity-ratings/<int:rating_id>', methods=['DELETE'])
@token_required
def delete_activity_rating(rating_id):
    """删除活动评分"""
    try:
        rating = ActivityRating.query.get(rating_id)
        if not rating:
            return jsonify({
                'success': False,
                'message': '评分不存在',
                'data': None
            }), 404

        db.session.delete(rating)
        db.session.commit()

        print(f"【活动评分删除成功】ID: {rating_id}")
        return jsonify({
            'success': True,
            'message': '活动评分删除成功',
            'data': None
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"【活动评分删除异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除失败：{str(e)}',
            'data': None
        }), 500






# 批量更新用户显示信息接口（用于用户注销后的匿名化处理）
@admin_bp.route('/activity/update-user-displays', methods=['POST'])
@token_required
def update_activity_user_displays():
    """批量更新活动相关的用户显示信息（处理用户注销情况）"""
    try:
        # 更新活动组织者显示信息
        activities = Activity.query.filter(Activity.organizer_user_id.isnot(None)).all()
        updated_activities = 0

        for activity in activities:
            old_display = activity.organizer_display
            activity.update_organizer_display()
            if old_display != activity.organizer_display:
                updated_activities += 1

        # 更新活动评分用户显示信息
        ratings = ActivityRating.query.filter(ActivityRating.rater_user_id.isnot(None)).all()
        updated_ratings = 0

        for rating in ratings:
            old_display = rating.rater_display
            rating.update_rater_display()
            if old_display != rating.rater_display:
                updated_ratings += 1

  
        db.session.commit()

        result = {
            'updated_activities': updated_activities,
            'updated_ratings': updated_ratings,
            'message': f'批量更新完成：活动{updated_activities}个，评分{updated_ratings}个'
        }

        print(f"【批量更新用户显示信息完成】{result['message']}")
        return jsonify({
            'success': True,
            'message': result['message'],
            'data': result
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"【批量更新用户显示信息异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量更新失败：{str(e)}',
            'data': None
        }), 500

