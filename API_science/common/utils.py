

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from flask import request, jsonify
from components import db
from components.models import ScienceArticle, ScienceArticleLike, ScienceArticleVisit, User, Admin
from components.response_service import ResponseService


def validate_article_data(data: Dict[str, Any], require_all: bool = True) -> tuple:
    
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
    
    if hasattr(current_user, 'role'):
        admin = Admin.query.filter_by(account=current_user.account).first()
        if admin:
            return admin.id, 'admin', admin

    if hasattr(current_user, 'is_deleted'):
        return current_user.id, 'user', current_user

    return None, None, None


def record_article_visit(article_id: int, current_user) -> tuple:
    
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