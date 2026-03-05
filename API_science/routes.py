# API_science/routes.py
# 科普模块 - 统一路由文件
# 包含所有子模块的路由和工具函数

from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from flask import request, Blueprint
from functools import wraps
from sqlalchemy import or_, func

from components import db, token_required
from components.models import (
    ScienceArticle, ScienceArticleLike, ScienceArticleVisit,
    User, Admin
)
from components.response_service import ResponseService


# ============================================================================
# 工具函数
# ============================================================================

def validate_article_data(data: Dict[str, Any], require_all: bool = True) -> tuple:
    """校验文章数据"""
    if not data:
        return False, "请求数据不能为空"

    if require_all:
        if not data.get('title', '').strip():
            return False, "标题不能为空"
        if not data.get('content', '').strip():
            return False, "内容不能为空"

    if 'status' in data:
        valid_statuses = ['draft', 'pending', 'published', 'rejected']
        if data['status'] not in valid_statuses:
            return False, f"状态无效，必须是: {', '.join(valid_statuses)}"

    if 'title' in data:
        title = data['title'].strip()
        if len(title) > 200:
            return False, "标题长度不能超过200个字符"

    if 'cover_image' in data and data['cover_image']:
        cover_image = data['cover_image'].strip()
        if len(cover_image) > 255:
            return False, "封面图片URL长度不能超过255个字符"

    return True, None


def get_user_identifier(current_user) -> tuple:
    """获取用户标识符和用户类型"""
    if hasattr(current_user, 'role'):
        admin = Admin.query.filter_by(account=current_user.account).first()
        if admin:
            return admin.id, 'admin', admin

    if hasattr(current_user, 'is_deleted'):
        return current_user.id, 'user', current_user

    return None, None, None


def record_article_visit(article_id: int, current_user) -> tuple:
    """记录文章浏览记录（避免重复记录）"""
    try:
        user_id, user_type, _ = get_user_identifier(current_user)
        if not user_id:
            return False, "用户身份验证失败", None

        article = ScienceArticle.query.get(article_id)
        if not article:
            return False, "文章不存在", None

        visit_record = None
        if user_type == 'admin':
            visit_record = ScienceArticleVisit.query.filter_by(admin_id=user_id, article_id=article_id).first()
        else:
            visit_record = ScienceArticleVisit.query.filter_by(user_id=user_id, article_id=article_id).first()

        if visit_record:
            visit_record.last_visit_at = datetime.now()
            action = "更新浏览记录"
        else:
            if user_type == 'admin':
                visit_record = ScienceArticleVisit(admin_id=user_id, article_id=article_id)
            else:
                visit_record = ScienceArticleVisit(user_id=user_id, article_id=article_id)
            db.session.add(visit_record)
            action = "新增浏览记录"

        db.session.commit()

        visit_data = {
            'article_id': article_id,
            'action': action,
            'first_visit_at': visit_record.first_visit_at.isoformat().replace('+00:00', 'Z'),
            'last_visit_at': visit_record.last_visit_at.isoformat().replace('+00:00', 'Z')
        }

        return True, f'{action}成功', visit_data

    except Exception as e:
        db.session.rollback()
        return False, f'浏览记录操作失败: {str(e)}', None


def toggle_article_like(article_id: int, current_user) -> tuple:
    """切换文章点赞状态"""
    try:
        user_id, user_type, _ = get_user_identifier(current_user)
        if not user_id:
            return False, "用户身份验证失败", None

        article = ScienceArticle.query.get(article_id)
        if not article:
            return False, "文章不存在", None

        like_record = None
        if user_type == 'admin':
            like_record = ScienceArticleLike.query.filter_by(admin_id=user_id, article_id=article_id).first()
        else:
            like_record = ScienceArticleLike.query.filter_by(user_id=user_id, article_id=article_id).first()

        if like_record:
            db.session.delete(like_record)
            article.like_count = max(0, (article.like_count or 0) - 1)
            action = "取消点赞"
            is_liked = False
        else:
            if user_type == 'admin':
                like_record = ScienceArticleLike(admin_id=user_id, article_id=article_id)
            else:
                like_record = ScienceArticleLike(user_id=user_id, article_id=article_id)
            db.session.add(like_record)
            article.like_count = (article.like_count or 0) + 1
            action = "点赞"
            is_liked = True

        db.session.commit()

        like_data = {
            'article_id': article_id,
            'like_count': article.like_count,
            'is_liked': is_liked,
            'action': action
        }

        return True, f'{action}成功', like_data

    except Exception as e:
        db.session.rollback()
        return False, f'点赞操作失败: {str(e)}', None


def get_like_status(article_ids: List[int], current_user) -> tuple:
    """获取用户对文章的点赞状态"""
    try:
        user_id, user_type, _ = get_user_identifier(current_user)
        if not user_id:
            return False, "用户身份验证失败", None

        if not article_ids:
            return False, "文章ID列表不能为空", None

        if user_type == 'admin':
            liked_records = ScienceArticleLike.query.filter(
                ScienceArticleLike.admin_id == user_id,
                ScienceArticleLike.article_id.in_(article_ids)
            ).all()
        else:
            liked_records = ScienceArticleLike.query.filter(
                ScienceArticleLike.user_id == user_id,
                ScienceArticleLike.article_id.in_(article_ids)
            ).all()

        like_status = {article_id: False for article_id in article_ids}
        for record in liked_records:
            like_status[record.article_id] = True

        status_data = {
            'article_like_status': like_status,
            'total_articles': len(article_ids),
            'liked_articles': len(liked_records)
        }

        return True, '点赞状态查询成功', status_data

    except Exception as e:
        return False, f'点赞状态查询失败: {str(e)}', None


def format_article_data(article: ScienceArticle, include_content: bool = True, include_like_status: bool = False, current_user=None) -> Dict[str, Any]:
    """格式化文章数据"""
    data = {
        'id': article.id,
        'title': article.title,
        'cover_image': article.cover_image,
        'status': article.status,
        'like_count': article.like_count or 0,
        'view_count': article.view_count or 0,
        'author_display': article.author_display,
        'published_at': article.published_at.isoformat().replace('+00:00', 'Z') if article.published_at else None,
        'created_at': article.created_at.isoformat().replace('+00:00', 'Z'),
        'updated_at': article.updated_at.isoformat().replace('+00:00', 'Z')
    }

    if include_content:
        data['content'] = article.content

    if include_like_status and current_user:
        success, _, status_data = get_like_status([article.id], current_user)
        if success and status_data:
            data['is_liked'] = status_data['article_like_status'].get(article.id, False)
        else:
            data['is_liked'] = False

    return data


def check_article_permission(article: ScienceArticle, current_user, require_admin: bool = False) -> tuple:
    """检查文章操作权限"""
    if require_admin:
        if not hasattr(current_user, 'role') or current_user.role != 'ADMIN':
            return False, "需要管理员权限"

    user_id, user_type, _ = get_user_identifier(current_user)
    if not user_id:
        return False, "用户身份验证失败"

    if user_type == 'admin':
        return True, None

    if article.author_user_id != user_id:
        return False, "无权限操作此文章"

    return True, None


def build_article_query(status: Optional[str] = None, keyword: Optional[str] = None, author_id: Optional[int] = None):
    """构建文章查询对象"""
    query = ScienceArticle.query

    if status:
        query = query.filter(ScienceArticle.status == status)

    if author_id:
        query = query.filter(ScienceArticle.author_user_id == author_id)

    if keyword:
        keyword = f'%{keyword}%'
        query = query.filter(
            (ScienceArticle.title.like(keyword)) |
            (ScienceArticle.content.like(keyword))
        )

    return query


def get_author_info(article: ScienceArticle) -> Dict[str, Any]:
    """获取文章作者信息"""
    author_info = {}
    if article.author_account:
        author = User.query.filter_by(account=article.author_account, is_deleted=0).first()
        if author:
            author_info = {
                'username': author.username,
                'avatar': author.avatar,
                'role_cn': '普通用户'
            }
        else:
            admin = Admin.query.filter_by(account=article.author_account).first()
            if admin:
                author_info = {
                    'username': admin.username,
                    'avatar': admin.avatar,
                    'role_cn': '管理员'
                }
    return author_info


# ============================================================================
# 蓝图定义
# ============================================================================

# 用户端科普操作蓝图
bp_science_user = Blueprint('bp_science_user', __name__, url_prefix='/api/science/user')

# 管理员科普管理蓝图
bp_science_admin = Blueprint('bp_science_admin', __name__, url_prefix='/api/science/admin')

# 科普业务公共接口蓝图
bp_science_category = Blueprint('bp_science_category', __name__, url_prefix='/api/science/category')

# 科普文章公开访问蓝图
bp_science_public = Blueprint('science_public', __name__, url_prefix='/api/public/science')


# ============================================================================
# 用户端科普操作路由
# ============================================================================

@bp_science_user.route('/articles', methods=['GET'])
def get_published_articles():
    """获取已发布的科普文章列表（公开接口）"""
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
    """获取科普文章详情（需要登录）"""
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
    """科普文章点赞/取消点赞接口"""
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
    """获取用户对文章的点赞状态"""
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
    """记录文章浏览接口"""
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
    """获取当前用户的科普文章列表"""
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
    """创建科普文章"""
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
            admin = Admin.query.get(user_id)
            if admin and admin.user_id:
                author_user_id = admin.user_id
        else:
            author_user_id = user_id

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
    """更新科普文章"""
    try:
        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

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
                article.published_at = datetime.utcnow()

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
    """删除科普文章（软删除，改为rejected状态）"""
    try:
        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

        has_permission, error_message = check_article_permission(article, current_user)
        if not has_permission:
            return ResponseService.error(error_message, status_code=403)

        article.status = 'rejected'
        article.updated_at = datetime.utcnow()

        db.session.commit()

        return ResponseService.success(message='科普文章删除成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'删除失败：{str(e)}', status_code=500)


# ============================================================================
# 管理员科普管理路由
# ============================================================================

def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(current_user, *args, **kwargs):
        if not hasattr(current_user, 'role') or current_user.role != 'ADMIN':
            return ResponseService.error('需要管理员权限', status_code=403)
        return f(current_user, *args, **kwargs)
    return decorated_function


@bp_science_admin.route('/articles', methods=['GET'])
@token_required
@admin_required
def get_all_articles(current_user):
    """管理员获取所有科普文章列表"""
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', '').strip()
        keyword = request.args.get('keyword', '').strip()
        author_id = request.args.get('author_id', '').strip()

        size = min(size, 50)

        query = build_article_query(status=status, keyword=keyword)

        if author_id and author_id.isdigit():
            query = query.filter(ScienceArticle.author_user_id == int(author_id))

        pagination = query.order_by(ScienceArticle.created_at.desc()).paginate(
            page=page, per_page=size, error_out=False
        )
        articles = pagination.items
        total = pagination.total

        result_list = []
        for article in articles:
            article_data = format_article_data(article, include_content=False)

            if article.author_user_id:
                author_user = User.query.get(article.author_user_id)
                if author_user:
                    article_data['author'] = {
                        'id': author_user.id,
                        'username': author_user.username,
                        'role': author_user.role,
                        'is_deleted': author_user.is_deleted
                    }

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


@bp_science_admin.route('/articles/<int:article_id>', methods=['GET'])
@token_required
@admin_required
def get_article_for_admin(current_user, article_id):
    """管理员获取文章详情（包含所有状态的文章）"""
    try:
        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

        article_data = format_article_data(article, include_content=True)

        if article.author_user_id:
            author_user = User.query.get(article.author_user_id)
            if author_user:
                article_data['author'] = {
                    'id': author_user.id,
                    'username': author_user.username,
                    'role': author_user.role,
                    'is_deleted': author_user.is_deleted,
                    'phone': author_user.phone,
                    'email': author_user.email
                }

        article_data['statistics'] = {
            'like_count': article.like_count or 0,
            'view_count': article.view_count or 0,
            'like_records_count': len(article.likes),
            'visit_records_count': len(article.visits)
        }

        return ResponseService.success(data=article_data, message='查询成功')

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_science_admin.route('/articles', methods=['POST'])
@token_required
@admin_required
def create_article_for_admin(current_user):
    """管理员创建科普文章"""
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        is_valid, error_message = validate_article_data(data, require_all=True)
        if not is_valid:
            return ResponseService.error(error_message, status_code=400)

        admin = Admin.query.filter_by(account=current_user.account).first()
        if not admin or not admin.user_id:
            return ResponseService.error('管理员关联用户信息异常', status_code=400)

        article = ScienceArticle(
            title=data['title'].strip(),
            content=data['content'].strip(),
            cover_image=data.get('cover_image', '').strip() if data.get('cover_image') else None,
            status=data.get('status', 'draft').strip(),
            author_user_id=admin.user_id,
            author_display=f"{current_user.username}（管理员）"
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


@bp_science_admin.route('/articles/<int:article_id>', methods=['PUT'])
@token_required
@admin_required
def update_article_for_admin(current_user, article_id):
    """管理员更新科普文章"""
    try:
        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        is_valid, error_message = validate_article_data(data, require_all=False)
        if not is_valid:
            return ResponseService.error(error_message, status_code=400)

        old_status = article.status

        if 'title' in data:
            article.title = data['title'].strip()
        if 'content' in data:
            article.content = data['content'].strip()
        if 'cover_image' in data:
            article.cover_image = data['cover_image'].strip() if data['cover_image'] else None
        if 'status' in data:
            article.status = data['status'].strip()

            if old_status != 'published' and article.status == 'published':
                article.published_at = datetime.utcnow()

        article.updated_at = datetime.utcnow()

        if old_status != article.status:
            print(f"【管理员文章状态变更】文章ID: {article_id}, 状态: {old_status} -> {article.status}, 操作管理员: {current_user.account}")

        db.session.commit()

        article_data = format_article_data(article, include_content=True)

        return ResponseService.success(data=article_data, message='科普文章更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'更新失败：{str(e)}', status_code=500)


@bp_science_admin.route('/articles/<int:article_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_article_for_admin(current_user, article_id):
    """管理员删除科普文章（硬删除）"""
    try:
        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

        ScienceArticleLike.query.filter_by(article_id=article_id).delete()
        ScienceArticleVisit.query.filter_by(article_id=article_id).delete()

        db.session.delete(article)

        print(f"【管理员删除文章】文章ID: {article_id}, 操作管理员: {current_user.account}")

        db.session.commit()

        return ResponseService.success(message='科普文章删除成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'删除失败：{str(e)}', status_code=500)


@bp_science_admin.route('/articles/<int:article_id>/approve', methods=['POST'])
@token_required
@admin_required
def approve_article(current_user, article_id):
    """管理员审核通过科普文章"""
    try:
        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

        if article.status != 'pending':
            return ResponseService.error('只能审核待审核状态的文章', status_code=400)

        article.status = 'published'
        article.published_at = datetime.utcnow()
        article.updated_at = datetime.utcnow()

        print(f"【管理员审核通过文章】文章ID: {article_id}, 操作管理员: {current_user.account}")

        db.session.commit()

        article_data = format_article_data(article, include_content=True)

        return ResponseService.success(data=article_data, message='文章审核通过')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'审核失败：{str(e)}', status_code=500)


@bp_science_admin.route('/articles/<int:article_id>/reject', methods=['POST'])
@token_required
@admin_required
def reject_article(current_user, article_id):
    """管理员审核驳回科普文章"""
    try:
        data = request.get_json() or {}
        reject_reason = data.get('reason', '').strip()

        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

        if article.status != 'pending':
            return ResponseService.error('只能审核待审核状态的文章', status_code=400)

        article.status = 'rejected'
        article.updated_at = datetime.utcnow()

        print(f"【管理员审核驳回文章】文章ID: {article_id}, 驳回原因: {reject_reason}, 操作管理员: {current_user.account}")

        db.session.commit()

        article_data = format_article_data(article, include_content=True)
        if reject_reason:
            article_data['reject_reason'] = reject_reason

        return ResponseService.success(data=article_data, message='文章审核驳回')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'审核失败：{str(e)}', status_code=500)


@bp_science_admin.route('/articles/batch-status', methods=['POST'])
@token_required
@admin_required
def batch_update_status(current_user):
    """批量更新文章状态"""
    try:
        data = request.get_json()
        if not data or not data.get('article_ids') or not data.get('status'):
            return ResponseService.error('缺少必要参数: article_ids 和 status', status_code=400)

        article_ids = data['article_ids']
        new_status = data['status'].strip()

        valid_statuses = ['draft', 'pending', 'published', 'rejected']
        if new_status not in valid_statuses:
            return ResponseService.error(f'无效的状态，必须是: {", ".join(valid_statuses)}', status_code=400)

        if not isinstance(article_ids, list) or not all(isinstance(id, int) for id in article_ids):
            return ResponseService.error('文章ID列表格式错误', status_code=400)

        articles = ScienceArticle.query.filter(ScienceArticle.id.in_(article_ids)).all()
        if not articles:
            return ResponseService.error('没有找到要更新的文章', status_code=404)

        updated_count = 0
        for article in articles:
            old_status = article.status
            article.status = new_status
            article.updated_at = datetime.utcnow()

            if new_status == 'published' and old_status != 'published':
                article.published_at = datetime.utcnow()

            updated_count += 1

        print(f"【管理员批量更新文章状态】文章数量: {updated_count}, 新状态: {new_status}, 操作管理员: {current_user.account}")

        db.session.commit()

        return ResponseService.success(
            data={
                'updated_count': updated_count,
                'total_requested': len(article_ids),
                'new_status': new_status
            },
            message=f'成功更新 {updated_count} 篇文章状态'
        )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'批量更新失败：{str(e)}', status_code=500)


@bp_science_admin.route('/articles/statistics', methods=['GET'])
@token_required
@admin_required
def get_articles_statistics(current_user):
    """获取科普文章统计信息"""
    try:
        total_articles = ScienceArticle.query.count()
        published_articles = ScienceArticle.query.filter_by(status='published').count()
        pending_articles = ScienceArticle.query.filter_by(status='pending').count()
        draft_articles = ScienceArticle.query.filter_by(status='draft').count()
        rejected_articles = ScienceArticle.query.filter_by(status='rejected').count()

        total_likes = db.session.query(db.func.sum(ScienceArticle.like_count)).scalar() or 0
        total_views = db.session.query(db.func.sum(ScienceArticle.view_count)).scalar() or 0

        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_articles = ScienceArticle.query.filter(
            ScienceArticle.created_at >= seven_days_ago
        ).count()

        pending_list = ScienceArticle.query.filter_by(status='pending').order_by(
            ScienceArticle.created_at.desc()
        ).limit(5).all()

        pending_data = []
        for article in pending_list:
            pending_data.append({
                'id': article.id,
                'title': article.title,
                'author_display': article.author_display,
                'created_at': article.created_at.isoformat().replace('+00:00', 'Z')
            })

        statistics = {
            'basic_stats': {
                'total_articles': total_articles,
                'published_articles': published_articles,
                'pending_articles': pending_articles,
                'draft_articles': draft_articles,
                'rejected_articles': rejected_articles,
                'recent_articles_7days': recent_articles
            },
            'interaction_stats': {
                'total_likes': int(total_likes),
                'total_views': int(total_views),
                'avg_likes_per_article': round(total_likes / max(total_articles, 1), 2),
                'avg_views_per_article': round(total_views / max(total_articles, 1), 2)
            },
            'pending_articles': pending_data
        }

        return ResponseService.success(data=statistics, message='统计信息查询成功')

    except Exception as e:
        return ResponseService.error(f'统计查询失败：{str(e)}', status_code=500)


# ============================================================================
# 科普业务公共接口路由
# ============================================================================

@bp_science_category.route('/articles/popular', methods=['GET'])
def get_popular_articles():
    """获取热门科普文章（基于点赞数和浏览数）"""
    try:
        limit = min(int(request.args.get('limit', 10)), 50)
        days = min(int(request.args.get('days', 30)), 365)

        start_date = datetime.utcnow() - timedelta(days=days)

        articles = ScienceArticle.query.filter(
            ScienceArticle.status == 'published',
            ScienceArticle.published_at >= start_date
        ).order_by(
            (ScienceArticle.like_count + ScienceArticle.view_count).desc(),
            ScienceArticle.published_at.desc()
        ).limit(limit).all()

        result_list = []
        for article in articles:
            article_data = format_article_data(article, include_content=False)
            article_data['popularity_score'] = (article.like_count or 0) + (article.view_count or 0)
            result_list.append(article_data)

        return ResponseService.success(
            data={
                'articles': result_list,
                'total': len(result_list),
                'time_range_days': days,
                'limit': limit
            },
            message='热门文章查询成功'
        )

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_science_category.route('/articles/latest', methods=['GET'])
def get_latest_articles():
    """获取最新发布的科普文章"""
    try:
        limit = min(int(request.args.get('limit', 10)), 50)

        articles = ScienceArticle.query.filter(
            ScienceArticle.status == 'published'
        ).order_by(
            ScienceArticle.published_at.desc()
        ).limit(limit).all()

        result_list = []
        for article in articles:
            article_data = format_article_data(article, include_content=False)
            if article.published_at:
                days_ago = (datetime.utcnow() - article.published_at).days
                if days_ago == 0:
                    article_data['publish_desc'] = '今天发布'
                elif days_ago == 1:
                    article_data['publish_desc'] = '昨天发布'
                elif days_ago <= 7:
                    article_data['publish_desc'] = f'{days_ago}天前发布'
                else:
                    article_data['publish_desc'] = f'{days_ago}天前发布'
            result_list.append(article_data)

        return ResponseService.success(
            data={
                'articles': result_list,
                'total': len(result_list),
                'limit': limit
            },
            message='最新文章查询成功'
        )

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_science_category.route('/articles/featured', methods=['GET'])
def get_featured_articles():
    """获取精选科普文章（高点赞数）"""
    try:
        limit = min(int(request.args.get('limit', 5)), 20)
        min_likes = max(int(request.args.get('min_likes', 10)), 1)

        articles = ScienceArticle.query.filter(
            ScienceArticle.status == 'published',
            ScienceArticle.like_count >= min_likes
        ).order_by(
            ScienceArticle.like_count.desc(),
            ScienceArticle.published_at.desc()
        ).limit(limit).all()

        result_list = []
        for article in articles:
            article_data = format_article_data(article, include_content=False)
            article_data['featured_score'] = article.like_count or 0
            result_list.append(article_data)

        return ResponseService.success(
            data={
                'articles': result_list,
                'total': len(result_list),
                'limit': limit,
                'min_likes': min_likes
            },
            message='精选文章查询成功'
        )

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_science_category.route('/articles/search', methods=['GET'])
def search_articles():
    """高级搜索科普文章"""
    try:
        page = int(request.args.get('page', 1))
        size = min(int(request.args.get('size', 20)), 50)
        keyword = request.args.get('keyword', '').strip()
        status = request.args.get('status', 'published').strip()
        min_likes = request.args.get('min_likes', '').strip()
        max_likes = request.args.get('max_likes', '').strip()
        min_views = request.args.get('min_views', '').strip()
        max_views = request.args.get('max_views', '').strip()
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        sort_by = request.args.get('sort_by', 'published_at').strip()
        sort_order = request.args.get('sort_order', 'desc').strip()

        query = build_article_query(status=status, keyword=keyword)

        if min_likes and min_likes.isdigit():
            query = query.filter(ScienceArticle.like_count >= int(min_likes))
        if max_likes and max_likes.isdigit():
            query = query.filter(ScienceArticle.like_count <= int(max_likes))

        if min_views and min_views.isdigit():
            query = query.filter(ScienceArticle.view_count >= int(min_views))
        if max_views and max_views.isdigit():
            query = query.filter(ScienceArticle.view_count <= int(max_views))

        if date_from:
            try:
                date_from_obj = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                query = query.filter(ScienceArticle.published_at >= date_from_obj)
            except ValueError:
                return ResponseService.error('起始日期格式错误', status_code=400)

        if date_to:
            try:
                date_to_obj = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                query = query.filter(ScienceArticle.published_at <= date_to_obj)
            except ValueError:
                return ResponseService.error('结束日期格式错误', status_code=400)

        sort_field = getattr(ScienceArticle, sort_by, ScienceArticle.published_at)
        if sort_order.lower() == 'desc':
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())

        pagination = query.paginate(page=page, per_page=size, error_out=False)
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
            message='搜索成功' if total > 0 else '没有找到符合条件的文章'
        )

    except Exception as e:
        return ResponseService.error(f'搜索失败：{str(e)}', status_code=500)


@bp_science_category.route('/articles/statistics', methods=['GET'])
def get_articles_statistics_public():
    """获取科普文章公开统计信息"""
    try:
        total_published = ScienceArticle.query.filter_by(status='published').count()

        published_stats = db.session.query(
            db.func.count(ScienceArticle.id).label('total_published'),
            db.func.sum(ScienceArticle.like_count).label('total_likes'),
            db.func.sum(ScienceArticle.view_count).label('total_views'),
            db.func.avg(ScienceArticle.like_count).label('avg_likes'),
            db.func.avg(ScienceArticle.view_count).label('avg_views')
        ).filter_by(status='published').first()

        status_stats = db.session.query(
            ScienceArticle.status,
            db.func.count(ScienceArticle.id).label('count')
        ).group_by(ScienceArticle.status).all()

        status_distribution = {status: count for status, count in status_stats}

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_stats = db.session.query(
            db.func.count(ScienceArticle.id).label('recent_published'),
            db.func.sum(ScienceArticle.like_count).label('recent_likes'),
            db.func.sum(ScienceArticle.view_count).label('recent_views')
        ).filter(
            ScienceArticle.status == 'published',
            ScienceArticle.published_at >= thirty_days_ago
        ).first()

        popular_keywords = ['健康', '科技', '环境', '生物', '物理', '化学', '医学', '天文']

        statistics = {
            'overview': {
                'total_published': published_stats.total_published or 0,
                'total_likes': int(published_stats.total_likes or 0),
                'total_views': int(published_stats.total_views or 0),
                'avg_likes_per_article': round(float(published_stats.avg_likes or 0), 2),
                'avg_views_per_article': round(float(published_stats.avg_views or 0), 2)
            },
            'status_distribution': status_distribution,
            'recent_activity': {
                'published_last_30_days': recent_stats.recent_published or 0,
                'likes_last_30_days': int(recent_stats.recent_likes or 0),
                'views_last_30_days': int(recent_stats.recent_views or 0)
            },
            'popular_keywords': popular_keywords
        }

        return ResponseService.success(data=statistics, message='统计信息查询成功')

    except Exception as e:
        return ResponseService.error(f'统计查询失败：{str(e)}', status_code=500)


@bp_science_category.route('/articles/recommendations', methods=['GET'])
def get_article_recommendations():
    """获取文章推荐（基于相似度）"""
    try:
        article_id = request.args.get('article_id', '').strip()
        limit = min(int(request.args.get('limit', 5)), 20)

        result_data = {
            'recommendations': [],
            'based_on': None
        }

        if article_id and article_id.isdigit():
            base_article = ScienceArticle.query.get(int(article_id))
            if base_article and base_article.status == 'published':
                result_data['based_on'] = {
                    'id': base_article.id,
                    'title': base_article.title
                }

                keywords = base_article.title.split()[:3]

                recommendations_query = ScienceArticle.query.filter(
                    ScienceArticle.status == 'published',
                    ScienceArticle.id != base_article.id
                )

                keyword_conditions = []
                for keyword in keywords:
                    if len(keyword) > 1:
                        keyword_conditions.append(ScienceArticle.title.like(f'%{keyword}%'))

                if keyword_conditions:
                    recommendations_query = recommendations_query.filter(or_(*keyword_conditions))

                recommendations = recommendations_query.order_by(
                    ScienceArticle.like_count.desc()
                ).limit(limit).all()

                result_data['recommendations'] = [
                    format_article_data(article, include_content=False)
                    for article in recommendations
                ]

        if not result_data['recommendations']:
            popular_articles = ScienceArticle.query.filter(
                ScienceArticle.status == 'published'
            ).order_by(
                (ScienceArticle.like_count + ScienceArticle.view_count).desc()
            ).limit(limit).all()

            result_data['recommendations'] = [
                format_article_data(article, include_content=False)
                for article in popular_articles
            ]

            if not result_data['based_on']:
                result_data['based_on'] = {'message': '基于热门度推荐'}

        return ResponseService.success(
            data=result_data,
            message='推荐文章获取成功'
        )

    except Exception as e:
        return ResponseService.error(f'推荐获取失败：{str(e)}', status_code=500)


@bp_science_category.route('/health', methods=['GET'])
def health_check():
    """科普模块健康检查接口"""
    try:
        article_count = ScienceArticle.query.count()

        health_status = {
            'status': 'healthy',
            'module': 'science_category',
            'timestamp': datetime.utcnow().isoformat(),
            'database': {
                'connected': True,
                'article_count': article_count
            },
            'endpoints': [
                '/api/science/category/articles/popular',
                '/api/science/category/articles/latest',
                '/api/science/category/articles/featured',
                '/api/science/category/articles/search',
                '/api/science/category/articles/statistics',
                '/api/science/category/articles/recommendations',
                '/api/science/category/health'
            ]
        }

        return ResponseService.success(data=health_status, message='科普模块运行正常')

    except Exception as e:
        return ResponseService.error(f'健康检查失败：{str(e)}', status_code=500)


# ============================================================================
# 科普文章公开访问路由
# ============================================================================

@bp_science_public.route('/articles', methods=['GET'])
def get_public_science_articles():
    """获取公开发布的科普文章列表（无需登录）"""
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        keyword = request.args.get('keyword', '').strip()
        author_account = request.args.get('author_account', '').strip()

        query = ScienceArticle.query.filter_by(status='published')

        if keyword:
            query = query.filter(
                (ScienceArticle.title.like(f'%{keyword}%')) |
                (ScienceArticle.content.like(f'%{keyword}%'))
            )

        if author_account:
            query = query.filter(ScienceArticle.author_account == author_account)

        pagination = query.order_by(ScienceArticle.published_at.desc()).paginate(page=page, per_page=size)
        articles = pagination.items
        total = pagination.total

        result_list = []
        for article in articles:
            author_info = get_author_info(article)

            item = {
                'id': article.id,
                'title': article.title,
                'summary': article.content[:200] + '...' if len(article.content) > 200 else article.content,
                'cover_image': article.cover_image,
                'like_count': article.like_count,
                'view_count': article.view_count,
                'published_at': article.published_at.isoformat().replace('+00:00', 'Z') if article.published_at else None,
                'created_at': article.created_at.isoformat().replace('+00:00', 'Z'),
                'author_account': article.author_account,
                'author_display': article.author_display,
                'author_info': author_info
            }
            result_list.append(item)

        return ResponseService.paginated_success(
            items=result_list,
            total=total,
            page=page,
            size=size,
            message="科普文章列表查询成功"
        )

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_science_public.route('/articles/<int:article_id>', methods=['GET'])
def get_public_science_article_detail(article_id):
    """获取公开发布的科普文章详情（无需登录）"""
    try:
        article = ScienceArticle.query.filter_by(id=article_id, status='published').first()
        if not article:
            return ResponseService.error('文章不存在或未发布', status_code=404)

        article.view_count += 1
        db.session.commit()

        author_info = get_author_info(article)

        item = {
            'id': article.id,
            'title': article.title,
            'content': article.content,
            'cover_image': article.cover_image,
            'like_count': article.like_count,
            'view_count': article.view_count,
            'published_at': article.published_at.isoformat().replace('+00:00', 'Z') if article.published_at else None,
            'created_at': article.created_at.isoformat().replace('+00:00', 'Z'),
            'updated_at': article.updated_at.isoformat().replace('+00:00', 'Z') if article.updated_at else None,
            'author_account': article.author_account,
            'author_display': article.author_display,
            'author_info': author_info
        }

        return ResponseService.success(data=item, message="科普文章详情查询成功")

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_science_public.route('/articles/statistics', methods=['GET'])
def get_public_science_statistics():
    """获取科普文章公开统计信息（无需登录）"""
    try:
        total_published = ScienceArticle.query.filter_by(status='published').count()

        published_stats = db.session.query(
            func.count(ScienceArticle.id).label('total_published'),
            func.sum(ScienceArticle.like_count).label('total_likes'),
            func.sum(ScienceArticle.view_count).label('total_views'),
            func.avg(ScienceArticle.like_count).label('avg_likes'),
            func.avg(ScienceArticle.view_count).label('avg_views')
        ).filter_by(status='published').first()

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_count = ScienceArticle.query.filter(
            ScienceArticle.status == 'published',
            ScienceArticle.published_at >= thirty_days_ago
        ).count()

        statistics = {
            'total_published': total_published or 0,
            'total_likes': int(published_stats.total_likes or 0),
            'total_views': int(published_stats.total_views or 0),
            'avg_likes': round(float(published_stats.avg_likes or 0), 2),
            'avg_views': round(float(published_stats.avg_views or 0), 2),
            'recent_published_30days': recent_count
        }

        return ResponseService.success(data=statistics, message="科普文章统计查询成功")

    except Exception as e:
        return ResponseService.error(f'统计查询失败：{str(e)}', status_code=500)
