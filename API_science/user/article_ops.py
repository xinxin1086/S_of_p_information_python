

from flask import request, Blueprint
from functools import wraps
from components import token_required, db
from components.models import ScienceArticle
from components.response_service import ResponseService
from API_science.common.utils import (
    record_article_visit,
    toggle_article_like,
    get_like_status,
    format_article_data,
    build_article_query,
    get_user_identifier,
    validate_article_data
)

bp_science_user = Blueprint('bp_science_user', __name__)


@bp_science_user.route('/articles', methods=['GET'])
def get_published_articles():
    
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', 'published').strip()
        keyword = request.args.get('keyword', '').strip()

        size = min(size, 50)

        query = build_article_query(status=status, keyword=keyword)

        pagination = query.order_by(ScienceArticle.published_at.desc(), ScienceArticle.created_at.desc()).paginate(
            page=page, per_page=size, error_out=False
        )
        articles = pagination.items
        total = pagination.total

        result_list = []
        for article in articles:
            article_data = format_article_data(article, include_content=False)
            result_list.append(article_data)

        return ResponseService.paginated_success(
            items=result_list,
            total=total,
            page=page,
            size=size,
            message='查询成功' if total > 0 else '暂无文章'
        )

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_science_user.route('/articles/<int:article_id>', methods=['GET'])
@token_required
def get_article_detail(current_user, article_id):
    
    try:
        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

        if article.status != 'published':
            return ResponseService.error('文章不可访问', status_code=403)

        article_data = format_article_data(
            article,
            include_content=True,
            include_like_status=True,
            current_user=current_user
        )

        try:
            record_article_visit(article_id, current_user)
        except Exception as visit_error:
            print(f"记录浏览记录失败: {str(visit_error)}")

        return ResponseService.success(data=article_data, message='查询成功')

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_science_user.route('/articles/like', methods=['POST'])
@token_required
def like_article(current_user):
    
    try:
        data = request.get_json()
        if not data or not data.get('article_id'):
            return ResponseService.error('缺少文章ID', status_code=400)

        article_id = data.get('article_id')

        success, message, like_data = toggle_article_like(article_id, current_user)
        if not success:
            return ResponseService.error(message, status_code=400)

        return ResponseService.success(data=like_data, message=message)

    except Exception as e:
        return ResponseService.error(f'操作失败：{str(e)}', status_code=500)


@bp_science_user.route('/articles/like/status', methods=['GET'])
@token_required
def get_article_like_status(current_user):
    
    try:
        article_ids_str = request.args.get('article_ids', '')
        if not article_ids_str:
            return ResponseService.error('缺少文章ID列表', status_code=400)

        try:
            article_ids = [int(id.strip()) for id in article_ids_str.split(',') if id.strip().isdigit()]
        except ValueError:
            return ResponseService.error('无效的文章ID格式', status_code=400)

        if not article_ids:
            return ResponseService.error('文章ID列表为空', status_code=400)

        success, message, status_data = get_like_status(article_ids, current_user)
        if not success:
            return ResponseService.error(message, status_code=400)

        return ResponseService.success(data=status_data, message=message)

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_science_user.route('/articles/visit', methods=['POST'])
@token_required
def record_visit(current_user):
    
    try:
        data = request.get_json()
        if not data or not data.get('article_id'):
            return ResponseService.error('缺少文章ID', status_code=400)

        article_id = data.get('article_id')

        success, message, visit_data = record_article_visit(article_id, current_user)
        if not success:
            return ResponseService.error(message, status_code=400)

        return ResponseService.success(data=visit_data, message=message)

    except Exception as e:
        return ResponseService.error(f'操作失败：{str(e)}', status_code=500)


@bp_science_user.route('/articles/my', methods=['GET'])
@token_required
def get_my_articles(current_user):
    
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', '').strip()
        keyword = request.args.get('keyword', '').strip()

        size = min(size, 50)

        user_id, user_type, _ = get_user_identifier(current_user)
        if not user_id:
            return ResponseService.error('用户身份验证失败', status_code=401)

        if user_type == 'admin':
            from components.models import Admin
            admin = Admin.query.get(user_id)
            if admin and admin.user_id:
                query = build_article_query(status=status, keyword=keyword, author_id=admin.user_id)
            else:
                query = build_article_query(status=status, keyword=keyword)
        else:
            query = build_article_query(status=status, keyword=keyword, author_id=user_id)

        pagination = query.order_by(ScienceArticle.updated_at.desc()).paginate(
            page=page, per_page=size, error_out=False
        )
        articles = pagination.items
        total = pagination.total

        result_list = []
        for article in articles:
            article_data = format_article_data(article, include_content=False)
            result_list.append(article_data)

        return ResponseService.paginated_success(
            items=result_list,
            total=total,
            page=page,
            size=size,
            message='查询成功' if total > 0 else '暂无文章'
        )

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_science_user.route('/articles', methods=['POST'])
@token_required
def create_article(current_user):
    
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        is_valid, error_message = validate_article_data(data, require_all=True)
        if not is_valid:
            return ResponseService.error(error_message, status_code=400)

        user_id, user_type, user_obj = get_user_identifier(current_user)
        if not user_id:
            return ResponseService.error('用户身份验证失败', status_code=401)

        author_user_id = None
        if user_type == 'admin':
            from components.models import Admin
            admin = Admin.query.get(user_id)
            if admin and admin.user_id:
                author_user_id = admin.user_id
        else:
            author_user_id = user_id

        from datetime import datetime
        article = ScienceArticle(
            title=data['title'].strip(),
            content=data['content'].strip(),
            cover_image=data.get('cover_image', '').strip() if data.get('cover_image') else None,
            status=data.get('status', 'draft').strip(),
            author_user_id=author_user_id,
            author_display=current_user.username
        )

        if article.status == 'published':
            article.published_at = datetime.utcnow()

        db.session.add(article)
        db.session.commit()

        article_data = format_article_data(article, include_content=True)

        return ResponseService.success(data=article_data, message='科普文章创建成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'创建失败：{str(e)}', status_code=500)


@bp_science_user.route('/articles/<int:article_id>', methods=['PUT'])
@token_required
def update_article(current_user, article_id):
    
    try:
        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

        from API_science.common.utils import check_article_permission
        has_permission, error_message = check_article_permission(article, current_user)
        if not has_permission:
            return ResponseService.error(error_message, status_code=403)

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        is_valid, error_message = validate_article_data(data, require_all=False)
        if not is_valid:
            return ResponseService.error(error_message, status_code=400)

        if 'title' in data:
            article.title = data['title'].strip()
        if 'content' in data:
            article.content = data['content'].strip()
        if 'cover_image' in data:
            article.cover_image = data['cover_image'].strip() if data['cover_image'] else None
        if 'status' in data:
            old_status = article.status
            article.status = data['status'].strip()

            if old_status != 'published' and article.status == 'published':
                from datetime import datetime
                article.published_at = datetime.utcnow()

        from datetime import datetime
        article.updated_at = datetime.utcnow()

        db.session.commit()

        article_data = format_article_data(article, include_content=True)

        return ResponseService.success(data=article_data, message='科普文章更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'更新失败：{str(e)}', status_code=500)


@bp_science_user.route('/articles/<int:article_id>', methods=['DELETE'])
@token_required
def delete_article(current_user, article_id):
    
    try:
        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

        from API_science.common.utils import check_article_permission
        has_permission, error_message = check_article_permission(article, current_user)
        if not has_permission:
            return ResponseService.error(error_message, status_code=403)

        article.status = 'rejected'
        from datetime import datetime
        article.updated_at = datetime.utcnow()

        db.session.commit()

        return ResponseService.success(message='科普文章删除成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'删除失败：{str(e)}', status_code=500)