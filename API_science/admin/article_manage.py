# API_science/admin/article_manage.py

"""
管理员科普文章管理接口
包含文章的创建、编辑、审核、删除等功能
"""

from flask import request, Blueprint
from functools import wraps
from components import token_required, db
from components.models import ScienceArticle, ScienceArticleLike, ScienceArticleVisit, User, Admin
from components.response_service import ResponseService
from API_science.common.utils import (
    format_article_data,
    build_article_query,
    check_article_permission,
    validate_article_data,
    get_user_identifier
)
from datetime import datetime

# 创建管理员科普蓝图
bp_science_admin = Blueprint('bp_science_admin', __name__, url_prefix='/api/science/admin')


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
        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', '').strip()
        keyword = request.args.get('keyword', '').strip()
        author_id = request.args.get('author_id', '').strip()

        # 限制每页最大数量
        size = min(size, 50)

        # 构建查询
        query = build_article_query(status=status, keyword=keyword)

        # 作者ID筛选
        if author_id and author_id.isdigit():
            query = query.filter(ScienceArticle.author_user_id == int(author_id))

        # 分页查询（按创建时间倒序）
        pagination = query.order_by(ScienceArticle.created_at.desc()).paginate(
            page=page, per_page=size, error_out=False
        )
        articles = pagination.items
        total = pagination.total

        # 格式化文章数据（包含作者信息）
        result_list = []
        for article in articles:
            article_data = format_article_data(article, include_content=False)

            # 添加作者详细信息
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
        # 查询文章
        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

        # 格式化文章数据（包含内容和作者信息）
        article_data = format_article_data(article, include_content=True)

        # 添加作者详细信息
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

        # 添加统计信息
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

        # 验证文章数据
        is_valid, error_message = validate_article_data(data, require_all=True)
        if not is_valid:
            return ResponseService.error(error_message, status_code=400)

        # 获取管理员关联的用户ID
        admin = Admin.query.filter_by(account=current_user.account).first()
        if not admin or not admin.user_id:
            return ResponseService.error('管理员关联用户信息异常', status_code=400)

        # 创建文章
        article = ScienceArticle(
            title=data['title'].strip(),
            content=data['content'].strip(),
            cover_image=data.get('cover_image', '').strip() if data.get('cover_image') else None,
            status=data.get('status', 'draft').strip(),
            author_user_id=admin.user_id,
            author_display=f"{current_user.username}（管理员）"
        )

        # 如果状态为已发布，设置发布时间
        if article.status == 'published':
            article.published_at = datetime.utcnow()

        db.session.add(article)
        db.session.commit()

        # 格式化返回数据
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
        # 查询文章
        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

        # 获取请求数据
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        # 验证更新的数据
        is_valid, error_message = validate_article_data(data, require_all=False)
        if not is_valid:
            return ResponseService.error(error_message, status_code=400)

        # 记录状态变更（用于审核日志）
        old_status = article.status

        # 更新字段
        if 'title' in data:
            article.title = data['title'].strip()
        if 'content' in data:
            article.content = data['content'].strip()
        if 'cover_image' in data:
            article.cover_image = data['cover_image'].strip() if data['cover_image'] else None
        if 'status' in data:
            article.status = data['status'].strip()

            # 如果状态从非发布改为发布，设置发布时间
            if old_status != 'published' and article.status == 'published':
                article.published_at = datetime.utcnow()

        # 更新时间
        article.updated_at = datetime.utcnow()

        # 如果有状态变更，记录管理员操作
        if old_status != article.status:
            print(f"【管理员文章状态变更】文章ID: {article_id}, 状态: {old_status} -> {article.status}, 操作管理员: {current_user.account}")

        db.session.commit()

        # 格式化返回数据
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
        # 查询文章
        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

        # 删除相关点赞记录
        ScienceArticleLike.query.filter_by(article_id=article_id).delete()

        # 删除相关浏览记录
        ScienceArticleVisit.query.filter_by(article_id=article_id).delete()

        # 删除文章
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
        # 查询文章
        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

        # 只能审核待审核的文章
        if article.status != 'pending':
            return ResponseService.error('只能审核待审核状态的文章', status_code=400)

        # 更新状态为已发布
        article.status = 'published'
        article.published_at = datetime.utcnow()
        article.updated_at = datetime.utcnow()

        print(f"【管理员审核通过文章】文章ID: {article_id}, 操作管理员: {current_user.account}")

        db.session.commit()

        # 格式化返回数据
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

        # 查询文章
        article = ScienceArticle.query.get(article_id)
        if not article:
            return ResponseService.error('文章不存在', status_code=404)

        # 只能审核待审核的文章
        if article.status != 'pending':
            return ResponseService.error('只能审核待审核状态的文章', status_code=400)

        # 更新状态为已驳回
        article.status = 'rejected'
        article.updated_at = datetime.utcnow()

        print(f"【管理员审核驳回文章】文章ID: {article_id}, 驳回原因: {reject_reason}, 操作管理员: {current_user.account}")

        db.session.commit()

        # 格式化返回数据
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

        # 验证状态有效性
        valid_statuses = ['draft', 'pending', 'published', 'rejected']
        if new_status not in valid_statuses:
            return ResponseService.error(f'无效的状态，必须是: {", ".join(valid_statuses)}', status_code=400)

        # 验证文章ID格式
        if not isinstance(article_ids, list) or not all(isinstance(id, int) for id in article_ids):
            return ResponseService.error('文章ID列表格式错误', status_code=400)

        # 查询要更新的文章
        articles = ScienceArticle.query.filter(ScienceArticle.id.in_(article_ids)).all()
        if not articles:
            return ResponseService.error('没有找到要更新的文章', status_code=404)

        # 批量更新
        updated_count = 0
        for article in articles:
            old_status = article.status
            article.status = new_status
            article.updated_at = datetime.utcnow()

            # 如果状态改为发布，设置发布时间
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
        # 基本统计
        total_articles = ScienceArticle.query.count()
        published_articles = ScienceArticle.query.filter_by(status='published').count()
        pending_articles = ScienceArticle.query.filter_by(status='pending').count()
        draft_articles = ScienceArticle.query.filter_by(status='draft').count()
        rejected_articles = ScienceArticle.query.filter_by(status='rejected').count()

        # 点赞和浏览统计
        total_likes = db.session.query(db.func.sum(ScienceArticle.like_count)).scalar() or 0
        total_views = db.session.query(db.func.sum(ScienceArticle.view_count)).scalar() or 0

        # 最近7天发布的文章数
        from datetime import timedelta
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_articles = ScienceArticle.query.filter(
            ScienceArticle.created_at >= seven_days_ago
        ).count()

        # 待审核文章列表（最新的5篇）
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
