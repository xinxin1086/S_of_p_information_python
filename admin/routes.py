#  ./admin/routes.py

import os
import jwt
from datetime import datetime, timedelta
from flask import request, jsonify
from config import Config
from components import db, token_required, LocalImageStorage  # 引用公共组件
from components.models import (
    Admin, User, Notice, ScienceArticle, Activity,
    ActivityBooking, ActivityComment, ForumPost,
    ForumComment, UserLike, Attachment
)  # 新增Notice和其他模型引用
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
                'user': {'id': user.id, 'account': user.account, 'name': user.username},
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


# 管理员数据增删改查接口（整合公告增删改功能）
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
        supported_tables = {
            'admin_info': Admin,
            'user_info': User,
            'notice': Notice,
            'science_articles': ScienceArticle,
            'activities': Activity,
            'activity': Activity,  # 添加单数形式支持
            'activity_bookings': ActivityBooking,
            'activity_comments': ActivityComment,
            'forum_posts': ForumPost,
            'forum_comments': ForumComment,
            'user_likes': UserLike,
            'attachments': Attachment
        }

        if table_name not in supported_tables:
            return jsonify({'success': False, 'message': f'不支持的表：{table_name}', 'data': None}), 400
        model = supported_tables[table_name]
        result = None

        # -------------------------- 全局时间解析函数（提升作用域）--------------------------
        def parse_notice_time(time_str):
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
        # ----------------------------------------------------------------------------------

        # 新增操作（支持用户和公告）
        if operate_type == 'add':
            # 按表名区分必填字段
            if table_name in ['admin_info', 'user_info']:
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

            elif table_name == 'notice':
                required_fields = ['release_title', 'release_notice', 'notice_type']
                for field in required_fields:
                    if field not in kwargs or not str(kwargs[field]).strip():
                        return jsonify({'success': False, 'message': f'缺少必填字段：{field}', 'data': None}), 400

                # 发布时间自动设置为当前时间（不可变更）
                release_time = datetime.now()
                expiration = kwargs.get('expiration')

                # 过滤掉 Notice 模型中不存在的字段（如 status）
                valid_kwargs = {
                    'release_title': kwargs['release_title'],
                    'release_notice': kwargs['release_notice'],
                    'notice_type': kwargs['notice_type']
                }

                new_record = Notice(
                    release_time=release_time,
                    update_time=datetime.now(),  # 初始更新时间=发布时间
                    expiration=parse_notice_time(expiration) if expiration else None,
                    **valid_kwargs
                )
                db.session.add(new_record)
                db.session.commit()
                result = {'id': new_record.id, 'message': '公告新增成功'}
                print(f"【公告创建成功】ID: {new_record.id}, 发布时间: {new_record.release_time.isoformat()}")

            # 科普文章新增
            elif table_name == 'science_articles':
                required_fields = ['title', 'content', 'author_account']
                for field in required_fields:
                    if field not in kwargs or not str(kwargs[field]).strip():
                        return jsonify({'success': False, 'message': f'缺少必填字段：{field}', 'data': None}), 400

                new_record = ScienceArticle(
                    title=kwargs['title'],
                    content=kwargs['content'],
                    author_account=kwargs['author_account'],
                    cover_image=kwargs.get('cover_image'),
                    status=kwargs.get('status', 'draft'),
                    published_at=parse_notice_time(kwargs.get('published_at')) if kwargs.get('published_at') else None
                )
                db.session.add(new_record)
                db.session.commit()
                result = {'id': new_record.id, 'message': '科普文章新增成功'}
                print(f"【科普文章创建成功】ID: {new_record.id}")

            # 活动新增
            elif table_name in ['activities', 'activity']:
                required_fields = ['title', 'description', 'organizer_account', 'start_time', 'end_time']
                for field in required_fields:
                    if field not in kwargs or not str(kwargs[field]).strip():
                        return jsonify({'success': False, 'message': f'缺少必填字段：{field}', 'data': None}), 400

                new_record = Activity(
                    title=kwargs['title'],
                    description=kwargs['description'],
                    organizer_account=kwargs['organizer_account'],
                    location=kwargs.get('location'),
                    start_time=parse_notice_time(kwargs['start_time']),
                    end_time=parse_notice_time(kwargs['end_time']),
                    max_participants=kwargs.get('max_participants'),
                    status=kwargs.get('status', 'draft')
                )
                db.session.add(new_record)
                db.session.commit()
                result = {'id': new_record.id, 'message': '活动新增成功'}
                print(f"【活动创建成功】ID: {new_record.id}")

            # 论坛帖子新增
            elif table_name == 'forum_posts':
                required_fields = ['title', 'content', 'author_account']
                for field in required_fields:
                    if field not in kwargs or not str(kwargs[field]).strip():
                        return jsonify({'success': False, 'message': f'缺少必填字段：{field}', 'data': None}), 400

                new_record = ForumPost(
                    title=kwargs['title'],
                    content=kwargs['content'],
                    author_account=kwargs['author_account'],
                    category=kwargs.get('category', 'default'),
                    status=kwargs.get('status', 'published')
                )
                db.session.add(new_record)
                db.session.commit()
                result = {'id': new_record.id, 'message': '论坛帖子新增成功'}
                print(f"【论坛帖子创建成功】ID: {new_record.id}")

            # 其他表的基本新增（activity_bookings, activity_comments, forum_comments, user_likes, attachments）
            else:
                # 根据不同表设置必填字段
                required_fields = []
                if table_name == 'activity_bookings':
                    required_fields = ['activity_id', 'user_account']
                elif table_name == 'activity_comments':
                    required_fields = ['activity_id', 'user_account', 'content']
                elif table_name == 'forum_comments':
                    required_fields = ['post_id', 'author_account', 'content']
                elif table_name == 'user_likes':
                    required_fields = ['user_account', 'target_type', 'target_id']
                elif table_name == 'attachments':
                    required_fields = ['uploader_account', 'file_name', 'file_path', 'file_size', 'file_type', 'usage_type']

                for field in required_fields:
                    if field not in kwargs or not str(kwargs[field]).strip():
                        return jsonify({'success': False, 'message': f'缺少必填字段：{field}', 'data': None}), 400

                # 处理特殊字段
                if 'activity_id' in kwargs:
                    kwargs['activity_id'] = int(kwargs['activity_id'])
                if 'post_id' in kwargs:
                    kwargs['post_id'] = int(kwargs['post_id'])
                if 'target_id' in kwargs:
                    kwargs['target_id'] = int(kwargs['target_id'])
                if 'file_size' in kwargs:
                    kwargs['file_size'] = int(kwargs['file_size'])
                if 'rating' in kwargs:
                    kwargs['rating'] = int(kwargs['rating'])

                new_record = model(**kwargs)
                db.session.add(new_record)
                db.session.commit()
                result = {'id': new_record.id, 'message': f'{table_name}新增成功'}
                print(f"【{table_name}创建成功】ID: {new_record.id}")

        # 删除操作（支持用户和公告）
        elif operate_type == 'delete':
            if table_name in ['admin_info', 'user_info']:
                records = model.query.filter_by(**kwargs).all()
                if records:
                    image_storage = LocalImageStorage()
                    for record in records:
                        if record.avatar:
                            filename = record.avatar.split('/')[-1]
                            image_storage.delete_image(filename)
                            print(f"【删除关联头像】文件名: {filename}")
                deleted_count = model.query.filter_by(**kwargs).delete()
                db.session.commit()
                result = {'deleted_count': deleted_count, 'message': f'删除{deleted_count}条用户记录'}

            elif table_name == 'notice':
                # 支持按 id 或 release_time 删除（id 优先）
                delete_kwargs = kwargs.copy()
                if 'id' in delete_kwargs:
                    delete_kwargs['id'] = int(delete_kwargs['id'])
                # 处理 release_time 条件（使用全局函数解析）
                if 'release_time' in delete_kwargs:
                    delete_kwargs['release_time'] = parse_notice_time(delete_kwargs['release_time'])
                deleted_count = Notice.query.filter_by(**delete_kwargs).delete()
                db.session.commit()
                result = {'deleted_count': deleted_count, 'message': f'删除{deleted_count}条公告记录'}
                print(f"【公告删除成功】条件：{delete_kwargs}，删除条数：{deleted_count}")

            # 删除其他模型数据
            elif table_name in ['science_articles', 'activities', 'activity_bookings', 'activity_comments', 'forum_posts', 'forum_comments', 'user_likes', 'attachments']:
                delete_kwargs = kwargs.copy()
                # 处理数字字段
                if 'id' in delete_kwargs:
                    delete_kwargs['id'] = int(delete_kwargs['id'])
                if 'activity_id' in delete_kwargs:
                    delete_kwargs['activity_id'] = int(delete_kwargs['activity_id'])
                if 'post_id' in delete_kwargs:
                    delete_kwargs['post_id'] = int(delete_kwargs['post_id'])
                if 'target_id' in delete_kwargs:
                    delete_kwargs['target_id'] = int(delete_kwargs['target_id'])

                # 处理时间字段
                if 'start_time' in delete_kwargs:
                    delete_kwargs['start_time'] = parse_notice_time(delete_kwargs['start_time'])
                if 'end_time' in delete_kwargs:
                    delete_kwargs['end_time'] = parse_notice_time(delete_kwargs['end_time'])
                if 'published_at' in delete_kwargs:
                    delete_kwargs['published_at'] = parse_notice_time(delete_kwargs['published_at'])

                deleted_count = model.query.filter_by(**delete_kwargs).delete()
                db.session.commit()
                result = {'deleted_count': deleted_count, 'message': f'删除{deleted_count}条{table_name}记录'}
                print(f"【{table_name}删除成功】条件：{delete_kwargs}，删除条数：{deleted_count}")

        # 更新操作（支持用户和公告，兼容edit/update类型）
        elif operate_type in ['update', 'edit']:
            if table_name in ['admin_info', 'user_info']:
                record_id = data.get('id')
                update_kwargs = data.get('kwargs', {}).copy()

                if not record_id:
                    return jsonify({'success': False, 'message': '缺少更新条件：id', 'data': None}), 400
                if not update_kwargs:
                    return jsonify({'success': False, 'message': '缺少更新内容：kwargs', 'data': None}), 400

                query_kwargs = {'id': int(record_id)}
                old_record = model.query.filter_by(**query_kwargs).first()
                if not old_record:
                    return jsonify({'success': False, 'message': f'未找到ID为{record_id}的记录', 'data': None}), 404

                # 处理密码更新
                if 'password' in update_kwargs:
                    new_password = update_kwargs.pop('password')
                    if new_password and new_password.strip():
                        old_record.set_password(new_password)
                        print(f"【更新密码】用户ID: {record_id} 的密码已更新")

                # 处理头像更新
                if 'avatar' in update_kwargs:
                    new_avatar = update_kwargs['avatar']
                    if not new_avatar or new_avatar.strip() == '':
                        if old_record.avatar:
                            filename = old_record.avatar.split('/')[-1]
                            LocalImageStorage().delete_image(filename)
                            print(f"【更新为空】删除旧头像：{filename}")
                    else:
                        if old_record.avatar:
                            filename = old_record.avatar.split('/')[-1]
                            LocalImageStorage().delete_image(filename)
                            print(f"【更新新头像】删除旧头像：{filename}")

                updated_count = model.query.filter_by(**query_kwargs).update(update_kwargs)
                db.session.commit()
                result = {'updated_count': updated_count, 'message': f'更新{updated_count}条用户记录'}

            elif table_name == 'notice':
                if operate_type == 'edit':
                    update_kwargs = kwargs.copy()
                    # 以自增ID作为查询条件
                    notice_id = data.get('id')
                    if not notice_id:
                        return jsonify({'success': False, 'message': '公告更新缺少主键：id', 'data': None}), 400
                    query_kwargs = {'id': int(notice_id)}

                    # 禁止修改发布时间
                    update_kwargs.pop('release_time', None)

                    # 核心修复：将 attachments 列表序列化为 JSON 字符串
                    if 'attachments' in update_kwargs:
                        try:
                            import json
                            update_kwargs['attachments'] = json.dumps(update_kwargs['attachments'])  # 列表 → JSON 字符串（如 [] → "[]"）
                        except Exception as e:
                            return jsonify({'success': False, 'message': f'附件格式错误：{str(e)}', 'data': None}), 400

                    # 处理到期时间
                    if 'expiration' in update_kwargs:
                        update_kwargs['expiration'] = parse_notice_time(update_kwargs['expiration']) if update_kwargs['expiration'] else None

                    update_kwargs.pop('id', None)

                else:
                    query_kwargs = data.get('query_kwargs', {})
                    update_kwargs = data.get('update_kwargs', {})
                    # 禁止修改发布时间
                    update_kwargs.pop('release_time', None)
                    # 处理时间字段
                    if 'expiration' in update_kwargs:
                        update_kwargs['expiration'] = parse_notice_time(update_kwargs['expiration']) if update_kwargs['expiration'] else None

                # 校验参数
                if not query_kwargs or not update_kwargs:
                    return jsonify({'success': False, 'message': '需同时提供查询条件和更新内容', 'data': None}), 400

                # 执行更新
                try:
                    existing_notice = Notice.query.filter_by(**query_kwargs).first()
                    if not existing_notice:
                        print(f"【公告更新失败】未找到ID为{query_kwargs.get('id')}的公告")
                        return jsonify({'success': False, 'message': '未找到待更新的公告', 'data': None}), 404

                    updated_count = Notice.query.filter_by(**query_kwargs).update(update_kwargs)
                    db.session.commit()
                    print(f"【公告更新成功】ID: {query_kwargs.get('id')}，影响条数：{updated_count}，更新内容：{update_kwargs}")
                    result = {'updated_count': updated_count, 'message': f'更新{updated_count}条公告记录'}
                except Exception as e:
                    db.session.rollback()
                    print(f"【公告更新异常】{str(e)}")
                    return jsonify({'success': False, 'message': f'更新失败：{str(e)}', 'data': None}), 500

            # 更新其他模型数据
            elif table_name in ['science_articles', 'activities', 'activity_bookings', 'activity_comments', 'forum_posts', 'forum_comments', 'user_likes', 'attachments']:
                if operate_type == 'edit':
                    update_kwargs = kwargs.copy()
                    record_id = data.get('id')
                    if not record_id:
                        return jsonify({'success': False, 'message': f'{table_name}更新缺少主键：id', 'data': None}), 400
                    query_kwargs = {'id': int(record_id)}
                    update_kwargs.pop('id', None)
                else:
                    query_kwargs = data.get('query_kwargs', {})
                    update_kwargs = data.get('update_kwargs', {})

                # 处理时间字段
                if 'start_time' in update_kwargs:
                    update_kwargs['start_time'] = parse_notice_time(update_kwargs['start_time']) if update_kwargs['start_time'] else None
                if 'end_time' in update_kwargs:
                    update_kwargs['end_time'] = parse_notice_time(update_kwargs['end_time']) if update_kwargs['end_time'] else None
                if 'published_at' in update_kwargs:
                    update_kwargs['published_at'] = parse_notice_time(update_kwargs['published_at']) if update_kwargs['published_at'] else None

                # 处理数字字段
                if 'activity_id' in update_kwargs:
                    update_kwargs['activity_id'] = int(update_kwargs['activity_id']) if update_kwargs['activity_id'] else None
                if 'post_id' in update_kwargs:
                    update_kwargs['post_id'] = int(update_kwargs['post_id']) if update_kwargs['post_id'] else None
                if 'target_id' in update_kwargs:
                    update_kwargs['target_id'] = int(update_kwargs['target_id']) if update_kwargs['target_id'] else None
                if 'file_size' in update_kwargs:
                    update_kwargs['file_size'] = int(update_kwargs['file_size']) if update_kwargs['file_size'] else None
                if 'max_participants' in update_kwargs:
                    update_kwargs['max_participants'] = int(update_kwargs['max_participants']) if update_kwargs['max_participants'] else None
                if 'rating' in update_kwargs:
                    update_kwargs['rating'] = int(update_kwargs['rating']) if update_kwargs['rating'] else None

                # 处理查询条件中的数字字段
                if 'id' in query_kwargs:
                    query_kwargs['id'] = int(query_kwargs['id'])
                if 'activity_id' in query_kwargs:
                    query_kwargs['activity_id'] = int(query_kwargs['activity_id'])
                if 'post_id' in query_kwargs:
                    query_kwargs['post_id'] = int(query_kwargs['post_id'])

                # 校验参数
                if not query_kwargs or not update_kwargs:
                    return jsonify({'success': False, 'message': '需同时提供查询条件和更新内容', 'data': None}), 400

                try:
                    existing_record = model.query.filter_by(**query_kwargs).first()
                    if not existing_record:
                        print(f"【{table_name}更新失败】未找到符合条件的记录")
                        return jsonify({'success': False, 'message': '未找到待更新的记录', 'data': None}), 404

                    updated_count = model.query.filter_by(**query_kwargs).update(update_kwargs)
                    db.session.commit()
                    print(f"【{table_name}更新成功】条件：{query_kwargs}，影响条数：{updated_count}，更新内容：{update_kwargs}")
                    result = {'updated_count': updated_count, 'message': f'更新{updated_count}条{table_name}记录'}
                except Exception as e:
                    db.session.rollback()
                    print(f"【{table_name}更新异常】{str(e)}")
                    return jsonify({'success': False, 'message': f'更新失败：{str(e)}', 'data': None}), 500

        # 列表查询操作
        elif operate_type == 'list':
            # list 操作与 query 操作逻辑相同，复用 query 的处理逻辑
            if table_name == 'notice':
                # 公告列表查询
                page = int(data.get('page', 1))
                size = int(data.get('size', 10))
                query = Notice.query

                # 公告多条件筛选
                if 'title' in kwargs:
                    query = query.filter(Notice.release_title.like(f"%{kwargs['title']}%"))
                if 'notice_type' in kwargs:
                    query = query.filter(Notice.notice_type == kwargs['notice_type'])
                if 'expiration_start' in kwargs:
                    start_time = parse_notice_time(kwargs['expiration_start'])
                    if start_time:
                        query = query.filter(Notice.expiration >= start_time)

                pagination = query.order_by(Notice.release_time.desc()).paginate(page=page, per_page=size)
                notices = pagination.items
                total = pagination.total

                result_list = []
                for notice in notices:
                    # 反序列化：JSON 字符串 → Python 列表（如 "[]" → []）
                    try:
                        import json
                        attachments = json.loads(notice.attachments) if notice.attachments else []
                    except Exception as e:
                        print(f"【附件反序列化失败】notice_id: {notice.id}, error: {str(e)}")
                        attachments = []

                    result_list.append({
                        'id': notice.id,
                        'release_time': notice.release_time.isoformat().replace('+00:00', 'Z'),
                        'update_time': notice.update_time.isoformat().replace('+00:00', 'Z'),
                        'release_title': notice.release_title,
                        'release_notice': notice.release_notice,
                        'expiration': notice.expiration.isoformat().replace('+00:00', 'Z') if notice.expiration else None,
                        'notice_type': notice.notice_type,
                        'attachments': attachments  # 返回数组给前端，前端可直接使用
                    })

                result = {
                    'total': total,
                    'page': page,
                    'size': size,
                    'items': result_list,
                    'message': '公告列表查询成功'
                }
            else:
                # 其他表的 list 操作，使用与 query 相同的逻辑
                page = int(data.get('page', 1))
                size = int(data.get('size', 10))
                query = model.query

                # 简单的条件筛选
                filter_kwargs = {}
                for key, value in kwargs.items():
                    if hasattr(model, key) and value != '' and value is not None:
                        filter_kwargs[key] = value

                if filter_kwargs:
                    query = query.filter_by(**filter_kwargs)

                pagination = query.order_by(model.id.desc()).paginate(page=page, per_page=size)
                items = pagination.items
                total = pagination.total

                result_list = []
                for item in items:
                    item_data = {}
                    for column in item.__table__.columns:
                        value = getattr(item, column.name)
                        if value is not None:
                            if column.type.__class__.__name__ in ['DateTime', 'TIMESTAMP']:
                                if hasattr(value, 'isoformat'):
                                    item_data[column.name] = value.isoformat().replace('+00:00', 'Z')
                                else:
                                    item_data[column.name] = str(value)
                            else:
                                item_data[column.name] = value
                        else:
                            item_data[column.name] = None
                    result_list.append(item_data)

                result = {
                    'total': total,
                    'page': page,
                    'size': size,
                    'items': result_list,
                    'message': f'{table_name}列表查询成功'
                }

        # 详情查询操作
        elif operate_type == 'detail':
            record_id = data.get('id')
            if not record_id:
                return jsonify({'success': False, 'message': '详情查询缺少参数：id', 'data': None}), 400

            record_id = int(record_id)
            record = model.query.filter_by(id=record_id).first()

            if not record:
                return jsonify({'success': False, 'message': f'未找到ID为{record_id}的记录', 'data': None}), 404

            # 构建返回数据
            item_data = {}
            for column in record.__table__.columns:
                value = getattr(record, column.name)
                if value is not None:
                    # 处理时间字段
                    if column.type.__class__.__name__ in ['DateTime', 'TIMESTAMP']:
                        if hasattr(value, 'isoformat'):
                            item_data[column.name] = value.isoformat().replace('+00:00', 'Z')
                        else:
                            item_data[column.name] = str(value)
                    # 处理 attachments 字段的反序列化（仅针对 notice 表）
                    elif column.name == 'attachments' and table_name == 'notice':
                        try:
                            import json
                            item_data[column.name] = json.loads(value) if value else []
                        except Exception as e:
                            print(f"【详情附件反序列化失败】table: {table_name}, id: {record.id}, error: {str(e)}")
                            item_data[column.name] = []
                    else:
                        item_data[column.name] = value
                else:
                    item_data[column.name] = None

                # 特殊处理 notice 表的 attachments 字段（当值为 None 时）
                if column.name == 'attachments' and table_name == 'notice' and item_data[column.name] is None:
                    item_data[column.name] = []

            result = {
                'item': item_data,
                'message': f'{table_name}详情查询成功'
            }

        # 查询操作（仅支持用户/管理员，公告查询用公开接口）
        elif operate_type == 'query':
            if table_name == 'admin_info':
                # 管理员列表查询
                page = int(data.get('page', 1))
                size = int(data.get('size', 10))
                # 支持按 account/username/phone 筛选
                filter_kwargs = kwargs.copy()
                pagination = model.query.filter_by(**filter_kwargs).paginate(page=page, per_page=size)
                items = pagination.items
                total = pagination.total

                result_list = []
                for item in items:
                    result_list.append({
                        'id': item.id,
                        'account': item.account,
                        'username': item.username,
                        'phone': item.phone,
                        'email': item.email,
                        'avatar': item.avatar,
                        'role': item.role
                    })

                result = {
                    'total': total,
                    'page': page,
                    'size': size,
                    'items': result_list,
                    'message': '管理员列表查询成功'
                }
            elif table_name == 'notice':
                # 管理员查询公告（支持多条件筛选）
                page = int(data.get('page', 1))
                size = int(data.get('size', 10))
                query = Notice.query

                # 公告多条件筛选（复用 visit 接口逻辑）
                if 'notice_type' in kwargs:
                    query = query.filter(Notice.notice_type == kwargs['notice_type'])
                if 'release_title' in kwargs:
                    query = query.filter(Notice.release_title.like(f"%{kwargs['release_title']}%"))
                if 'release_time_start' in kwargs:
                    start_time = parse_notice_time(kwargs['release_time_start'])
                    if start_time:
                        query = query.filter(Notice.release_time >= start_time)
                if 'release_time_end' in kwargs:
                    end_time = parse_notice_time(kwargs['release_time_end'])
                    if end_time:
                        query = query.filter(Notice.release_time <= end_time)

                pagination = query.order_by(Notice.release_time.desc()).paginate(page=page, per_page=size)
                notices = pagination.items
                total = pagination.total

                result_list = []
                for notice in notices:
                    # 反序列化：JSON 字符串 → Python 列表（如 "[]" → []）
                    try:
                        import json
                        attachments = json.loads(notice.attachments) if notice.attachments else []
                    except Exception as e:
                        print(f"【附件反序列化失败】notice_id: {notice.id}, error: {str(e)}")
                        attachments = []

                    result_list.append({
                        'id': notice.id,
                        'release_time': notice.release_time.isoformat().replace('+00:00', 'Z'),
                        'update_time': notice.update_time.isoformat().replace('+00:00', 'Z'),
                        'release_title': notice.release_title,
                        'release_notice': notice.release_notice,
                        'expiration': notice.expiration.isoformat().replace('+00:00',
                                                                            'Z') if notice.expiration else None,
                        'notice_type': notice.notice_type,
                        'attachments': attachments  # 返回数组给前端，前端可直接使用
                    })

                result = {
                    'total': total,
                    'page': page,
                    'size': size,
                    'items': result_list,
                    'message': '公告列表查询成功'
                }
            elif table_name == 'user_info':
                # 普通用户列表查询（管理员权限）
                page = int(data.get('page', 1))
                size = int(data.get('size', 10))
                filter_kwargs = kwargs.copy()
                pagination = model.query.filter_by(**filter_kwargs).paginate(page=page, per_page=size)
                items = pagination.items
                total = pagination.total

                result_list = []
                for item in items:
                    result_list.append({
                        'id': item.id,
                        'account': item.account,
                        'username': item.username,
                        'phone': item.phone,
                        'email': item.email,
                        'avatar': item.avatar,
                        'role': item.role
                    })

                result = {
                    'total': total,
                    'page': page,
                    'size': size,
                    'items': result_list,
                    'message': '用户列表查询成功'
                }
            # 查询其他模型数据
            elif table_name in ['science_articles', 'activities', 'activity_bookings', 'activity_comments', 'forum_posts', 'forum_comments', 'user_likes', 'attachments']:
                page = int(data.get('page', 1))
                size = int(data.get('size', 10))
                query = model.query

                # 科普文章筛选
                if table_name == 'science_articles':
                    if 'author_account' in kwargs:
                        query = query.filter(ScienceArticle.author_account == kwargs['author_account'])
                    if 'status' in kwargs:
                        query = query.filter(ScienceArticle.status == kwargs['status'])
                    if 'title' in kwargs:
                        query = query.filter(ScienceArticle.title.like(f"%{kwargs['title']}%"))

                # 活动筛选
                elif table_name == 'activities':
                    if 'organizer_account' in kwargs:
                        query = query.filter(Activity.organizer_account == kwargs['organizer_account'])
                    if 'status' in kwargs:
                        query = query.filter(Activity.status == kwargs['status'])
                    if 'title' in kwargs:
                        query = query.filter(Activity.title.like(f"%{kwargs['title']}%"))

                # 活动预约筛选
                elif table_name == 'activity_bookings':
                    if 'activity_id' in kwargs:
                        query = query.filter(ActivityBooking.activity_id == int(kwargs['activity_id']))
                    if 'user_account' in kwargs:
                        query = query.filter(ActivityBooking.user_account == kwargs['user_account'])
                    if 'status' in kwargs:
                        query = query.filter(ActivityBooking.status == kwargs['status'])

                # 活动评论筛选
                elif table_name == 'activity_comments':
                    if 'activity_id' in kwargs:
                        query = query.filter(ActivityComment.activity_id == int(kwargs['activity_id']))
                    if 'user_account' in kwargs:
                        query = query.filter(ActivityComment.user_account == kwargs['user_account'])

                # 论坛帖子筛选
                elif table_name == 'forum_posts':
                    if 'author_account' in kwargs:
                        query = query.filter(ForumPost.author_account == kwargs['author_account'])
                    if 'category' in kwargs:
                        query = query.filter(ForumPost.category == kwargs['category'])
                    if 'status' in kwargs:
                        query = query.filter(ForumPost.status == kwargs['status'])
                    if 'title' in kwargs:
                        query = query.filter(ForumPost.title.like(f"%{kwargs['title']}%"))

                # 论坛评论筛选
                elif table_name == 'forum_comments':
                    if 'post_id' in kwargs:
                        query = query.filter(ForumComment.post_id == int(kwargs['post_id']))
                    if 'author_account' in kwargs:
                        query = query.filter(ForumComment.author_account == kwargs['author_account'])

                # 用户点赞筛选
                elif table_name == 'user_likes':
                    if 'user_account' in kwargs:
                        query = query.filter(UserLike.user_account == kwargs['user_account'])
                    if 'target_type' in kwargs:
                        query = query.filter(UserLike.target_type == kwargs['target_type'])
                    if 'target_id' in kwargs:
                        query = query.filter(UserLike.target_id == int(kwargs['target_id']))

                # 附件筛选
                elif table_name == 'attachments':
                    if 'uploader_account' in kwargs:
                        query = query.filter(Attachment.uploader_account == kwargs['uploader_account'])
                    if 'usage_type' in kwargs:
                        query = query.filter(Attachment.usage_type == kwargs['usage_type'])

                pagination = query.order_by(model.id.desc()).paginate(page=page, per_page=size)
                items = pagination.items
                total = pagination.total

                result_list = []
                for item in items:
                    item_data = {}
                    # 动态获取模型字段
                    for column in item.__table__.columns:
                        value = getattr(item, column.name)
                        if value is not None:
                            # 处理时间字段
                            if column.type.__class__.__name__ in ['DateTime', 'TIMESTAMP']:
                                if hasattr(value, 'isoformat'):
                                    item_data[column.name] = value.isoformat().replace('+00:00', 'Z')
                                else:
                                    item_data[column.name] = str(value)
                            else:
                                item_data[column.name] = value
                        else:
                            item_data[column.name] = None
                    result_list.append(item_data)

                result = {
                    'total': total,
                    'page': page,
                    'size': size,
                    'items': result_list,
                    'message': f'{table_name}列表查询成功'
                }

        # 统一返回成功结果
        return jsonify({
            'success': True,
            'message': result.get('message', '操作成功'),
            'data': result
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"【操作异常】{str(e)}")
        return jsonify({'success': False, 'message': f'操作失败：{str(e)}', 'data': None}), 500