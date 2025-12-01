# ./common/routes.py

from flask import request, jsonify
from components import token_required, LocalImageStorage, db  # 新增db导入
from components.models import Admin, User, ScienceArticle, Activity  # 导入模型
from common import common_bp
from sqlalchemy.exc import SQLAlchemyError  # 导入SQLAlchemy的错误处理


# 原有公共图片上传接口（保持不变）
@common_bp.route('/upload/image', methods=['POST'])
@token_required
def upload_image(current_user):
    try:
        print(f"【图片上传请求】用户: {current_user.account}")
        file = request.files.get('image')
        if not file:
            return jsonify({'success': False, 'message': '未获取到上传文件', 'data': None}), 400

        image_storage = LocalImageStorage()
        save_result = image_storage.save_image(file)

        if save_result['status'] != 'success':
            print(f"【图片上传失败】原因: {save_result['message']}")
            return jsonify({
                'success': False,
                'message': f'上传失败：{save_result["message"]}',
                'data': None
            }), 400

        print(f"【图片上传成功】URL: {save_result['url']}, 文件名: {save_result['filename']}")
        return jsonify({
            'success': True,
            'message': '图片上传成功',
            'data': {
                'image_url': save_result['url'],
                'filename': save_result['filename'],
                'file_path': save_result['file_path']
            }
        }), 200

    except Exception as e:
        print(f"【图片上传异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'上传异常：{str(e)}',
            'data': None
        }), 500


# 原有公共图片删除接口（保持不变）
@common_bp.route('/delete/image', methods=['POST'])
@token_required
def delete_image(current_user):
    try:
        data = request.get_json()
        filename = data.get('filename')
        image_url = data.get('image_url')

        # 提取文件名
        if not filename and image_url:
            filename = image_url.rsplit('/', 1)[-1]  # 使用rsplit以避免URL末尾斜杠的问题

        if not filename:
            return jsonify({'success': False, 'message': '缺少文件名（filename）或图片URL（image_url）', 'data': None}), 400

        image_storage = LocalImageStorage()
        delete_result = image_storage.delete_image(filename)

        if delete_result['status'] != 'success':
            print(f"【图片删除失败】原因: {delete_result['message']}")
            return jsonify({'success': False, 'message': delete_result['message'], 'data': None}), 400

        return jsonify({'success': True, 'message': '图片删除成功', 'data': None}), 200

    except Exception as e:
        print(f"【图片删除异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除异常：{str(e)}',
            'data': None
        }), 500


# 头像上传接口（仅用户创建成功后调用）
# 公共头像上传接口（修复旧头像删除）
@common_bp.route('/upload/avatar', methods=['POST'])
@token_required
def upload_user_avatar(current_user):
    try:
        print(f"【头像上传请求】用户: {current_user.account}")
        table_name = request.form.get('table_name')
        record_id = request.form.get('record_id')
        avatar_file = request.files.get('avatar')

        if not table_name or not record_id or not avatar_file:
            return jsonify({
                'success': False,
                'message': '缺少参数：table_name、record_id或avatar文件',
                'data': None
            }), 400

        supported_tables = {'admin_info': Admin, 'user_info': User}
        if table_name not in supported_tables:
            return jsonify({
                'success': False,
                'message': f'不支持的表：{table_name}，仅允许admin_info或user_info',
                'data': None
            }), 400
        model = supported_tables[table_name]

        # 查询旧记录（关键：获取旧头像URL）
        old_record = model.query.get(int(record_id))
        if not old_record:
            return jsonify({
                'success': False,
                'message': f'ID为{record_id}的{table_name}记录不存在',
                'data': None
            }), 404

        # 修复点2：上传新头像前，先删除旧头像
        if old_record.avatar:
            old_filename = old_record.avatar.split('/')[-1]
            LocalImageStorage().delete_image(old_filename)
            print(f"【上传新头像】删除旧头像：{old_filename}")

        # 保存新头像
        image_storage = LocalImageStorage()
        save_result = image_storage.save_image(avatar_file)
        if save_result['status'] != 'success':
            return jsonify({
                'success': False,
                'message': f'图片上传失败：{save_result["message"]}',
                'data': None
            }), 400

        # 更新新头像URL
        old_record.avatar = save_result['url']
        db.session.commit()
        print(f"【头像上传成功】{table_name} ID: {record_id}, 新头像URL: {save_result['url']}")

        return jsonify({
            'success': True,
            'message': '头像上传并关联成功（旧头像已删除）',
            'data': {
                'avatar_url': save_result['url'],
                'filename': save_result['filename']
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"【头像上传异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'头像上传失败：{str(e)}',
            'data': None
        }), 500


# 科普文章公开查询接口（无需登录）
@common_bp.route('/science/list', methods=['GET'])
def get_science_list():
    try:
        print(f"【科普文章查询请求】开始查询科普文章列表")

        # 获取分页和筛选参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        status = request.args.get('status', 'published')  # 默认只显示已发布的文章
        author_account = request.args.get('author_account')
        title = request.args.get('title')

        # 构建查询
        query = ScienceArticle.query

        # 只显示已发布的文章
        if status:
            query = query.filter(ScienceArticle.status == status)

        # 作者筛选
        if author_account:
            query = query.filter(ScienceArticle.author_account == author_account)

        # 标题模糊搜索
        if title:
            query = query.filter(ScienceArticle.title.like(f"%{title}%"))

        # 分页查询
        pagination = query.order_by(ScienceArticle.created_at.desc()).paginate(page=page, per_page=size)
        articles = pagination.items
        total = pagination.total

        result_list = []
        for article in articles:
            # 列表模式不显示内容信息，只显示基本信息
            item = {
                'id': article.id,
                'title': article.title,
                'author_account': article.author_account,
                'cover_image': article.cover_image,
                'status': article.status,
                'like_count': article.like_count,
                'view_count': article.view_count,
                'published_at': article.published_at.isoformat().replace('+00:00', 'Z') if article.published_at else None,
                'created_at': article.created_at.isoformat().replace('+00:00', 'Z')
            }
            result_list.append(item)

        result = {
            'total': total,
            'page': page,
            'size': size,
            'items': result_list,
            'message': '科普文章列表查询成功'
        }

        print(f"【科普文章查询成功】总数: {total}, 当前页: {page}, 页大小: {size}")
        return jsonify({
            'success': True,
            'message': result['message'],
            'data': result
        }), 200

    except Exception as e:
        print(f"【科普文章查询异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


# 科普文章详情查询接口（无需登录，包含完整内容）
@common_bp.route('/science/detail/<int:article_id>', methods=['GET'])
def get_science_detail(article_id):
    try:
        print(f"【科普文章详情查询】文章ID: {article_id}")

        article = ScienceArticle.query.filter_by(id=article_id, status='published').first()
        if not article:
            return jsonify({
                'success': False,
                'message': '文章不存在或未发布',
                'data': None
            }), 404

        # 增加浏览次数
        article.view_count += 1
        db.session.commit()

        # 返回完整信息，包括内容
        item = {
            'id': article.id,
            'title': article.title,
            'content': article.content,  # 详情页显示完整内容
            'author_account': article.author_account,
            'cover_image': article.cover_image,
            'status': article.status,
            'like_count': article.like_count,
            'view_count': article.view_count,
            'published_at': article.published_at.isoformat().replace('+00:00', 'Z') if article.published_at else None,
            'created_at': article.created_at.isoformat().replace('+00:00', 'Z'),
            'updated_at': article.updated_at.isoformat().replace('+00:00', 'Z')
        }

        print(f"【科普文章详情查询成功】文章标题: {article.title}")
        return jsonify({
            'success': True,
            'message': '科普文章详情查询成功',
            'data': item
        }), 200

    except Exception as e:
        print(f"【科普文章详情查询异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


# 活动公开查询接口（无需登录）
@common_bp.route('/activity/list', methods=['GET'])
def get_activity_list():
    try:
        print(f"【活动查询请求】开始查询活动列表")

        # 获取分页和筛选参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        status = request.args.get('status', 'published')  # 默认只显示已发布的活动
        organizer_account = request.args.get('organizer_account')
        title = request.args.get('title')

        # 构建查询
        query = Activity.query

        # 只显示已发布的活动
        if status:
            query = query.filter(Activity.status == status)

        # 组织者筛选
        if organizer_account:
            query = query.filter(Activity.organizer_account == organizer_account)

        # 标题模糊搜索
        if title:
            query = query.filter(Activity.title.like(f"%{title}%"))

        # 分页查询
        pagination = query.order_by(Activity.created_at.desc()).paginate(page=page, per_page=size)
        activities = pagination.items
        total = pagination.total

        result_list = []
        for activity in activities:
            # 列表模式不显示描述信息，只显示基本信息
            item = {
                'id': activity.id,
                'title': activity.title,
                'organizer_account': activity.organizer_account,
                'location': activity.location,
                'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
                'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
                'max_participants': activity.max_participants,
                'current_participants': activity.current_participants,
                'status': activity.status,
                'created_at': activity.created_at.isoformat().replace('+00:00', 'Z')
            }
            result_list.append(item)

        result = {
            'total': total,
            'page': page,
            'size': size,
            'items': result_list,
            'message': '活动列表查询成功'
        }

        print(f"【活动查询成功】总数: {total}, 当前页: {page}, 页大小: {size}")
        return jsonify({
            'success': True,
            'message': result['message'],
            'data': result
        }), 200

    except Exception as e:
        print(f"【活动查询异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


# 活动详情查询接口（无需登录，包含完整描述）
@common_bp.route('/activity/detail/<int:activity_id>', methods=['GET'])
def get_activity_detail(activity_id):
    try:
        print(f"【活动详情查询】活动ID: {activity_id}")

        activity = Activity.query.filter_by(id=activity_id, status='published').first()
        if not activity:
            return jsonify({
                'success': False,
                'message': '活动不存在或未发布',
                'data': None
            }), 404

        # 返回完整信息，包括描述
        item = {
            'id': activity.id,
            'title': activity.title,
            'description': activity.description,  # 详情页显示完整描述
            'organizer_account': activity.organizer_account,
            'location': activity.location,
            'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'max_participants': activity.max_participants,
            'current_participants': activity.current_participants,
            'status': activity.status,
            'created_at': activity.created_at.isoformat().replace('+00:00', 'Z'),
            'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z')
        }

        print(f"【活动详情查询成功】活动标题: {activity.title}")
        return jsonify({
            'success': True,
            'message': '活动详情查询成功',
            'data': item
        }), 200

    except Exception as e:
        print(f"【活动详情查询异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


