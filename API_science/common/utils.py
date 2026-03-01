# API_science/common/utils.py

"""
科普模块公共工具函数
包含参数校验、响应格式化、统计函数等通用功能
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from flask import request, jsonify
from components import db
from components.models import ScienceArticle, ScienceArticleLike, ScienceArticleVisit, User, Admin
from components.response_service import ResponseService


def validate_article_data(data: Dict[str, Any], require_all: bool = True) -> tuple:
    """
    校验文章数据

    Args:
        data: 请求数据
        require_all: 是否要求所有字段必填

    Returns:
        (is_valid, error_message)
    """
    if not data:
        return False, "请求数据不能为空"

    # 必填字段校验
    if require_all:
        if not data.get('title', '').strip():
            return False, "标题不能为空"
        if not data.get('content', '').strip():
            return False, "内容不能为空"

    # 可选字段格式校验
    if 'status' in data:
        valid_statuses = ['draft', 'pending', 'published', 'rejected']
        if data['status'] not in valid_statuses:
            return False, f"状态无效，必须是: {', '.join(valid_statuses)}"

    # 标题长度校验
    if 'title' in data:
        title = data['title'].strip()
        if len(title) > 200:
            return False, "标题长度不能超过200个字符"

    # URL格式校验（如果有封面图片）
    if 'cover_image' in data and data['cover_image']:
        cover_image = data['cover_image'].strip()
        if len(cover_image) > 255:
            return False, "封面图片URL长度不能超过255个字符"

    return True, None


def get_user_identifier(current_user) -> tuple:
    """
    获取用户标识符和用户类型

    Args:
        current_user: 当前用户对象

    Returns:
        (user_id, user_type, user_obj)
    """
    # 检查是否为管理员
    if hasattr(current_user, 'role'):
        admin = Admin.query.filter_by(account=current_user.account).first()
        if admin:
            return admin.id, 'admin', admin

    # 普通用户
    if hasattr(current_user, 'is_deleted'):
        return current_user.id, 'user', current_user

    return None, None, None


def record_article_visit(article_id: int, current_user) -> tuple:
    """
    记录文章浏览记录（避免重复记录）

    Args:
        article_id: 文章ID
        current_user: 当前用户

    Returns:
        (success, message, visit_data)
    """
    try:
        user_id, user_type, _ = get_user_identifier(current_user)
        if not user_id:
            return False, "用户身份验证失败", None

        # 检查文章是否存在
        article = ScienceArticle.query.get(article_id)
        if not article:
            return False, "文章不存在", None

        # 查找现有浏览记录
        visit_record = None
        if user_type == 'admin':
            visit_record = ScienceArticleVisit.query.filter_by(admin_id=user_id, article_id=article_id).first()
        else:
            visit_record = ScienceArticleVisit.query.filter_by(user_id=user_id, article_id=article_id).first()

        if visit_record:
            # 更新最后浏览时间
            visit_record.last_visit_at = datetime.now()
            action = "更新浏览记录"
        else:
            # 创建新浏览记录
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
    """
    切换文章点赞状态

    Args:
        article_id: 文章ID
        current_user: 当前用户

    Returns:
        (success, message, like_data)
    """
    try:
        user_id, user_type, _ = get_user_identifier(current_user)
        if not user_id:
            return False, "用户身份验证失败", None

        # 检查文章是否存在
        article = ScienceArticle.query.get(article_id)
        if not article:
            return False, "文章不存在", None

        # 查找现有点赞记录
        like_record = None
        if user_type == 'admin':
            like_record = ScienceArticleLike.query.filter_by(admin_id=user_id, article_id=article_id).first()
        else:
            like_record = ScienceArticleLike.query.filter_by(user_id=user_id, article_id=article_id).first()

        if like_record:
            # 取消点赞
            db.session.delete(like_record)
            article.like_count = max(0, (article.like_count or 0) - 1)
            action = "取消点赞"
            is_liked = False
        else:
            # 新增点赞
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
    """
    获取用户对文章的点赞状态

    Args:
        article_ids: 文章ID列表
        current_user: 当前用户

    Returns:
        (success, message, like_status_data)
    """
    try:
        user_id, user_type, _ = get_user_identifier(current_user)
        if not user_id:
            return False, "用户身份验证失败", None

        if not article_ids:
            return False, "文章ID列表不能为空", None

        # 查询用户对这些文章的点赞状态
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

        # 构建结果：文章ID -> 是否点赞
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
    """
    格式化文章数据

    Args:
        article: 文章对象
        include_content: 是否包含内容
        include_like_status: 是否包含点赞状态
        current_user: 当前用户（用于查询点赞状态）

    Returns:
        格式化后的文章数据
    """
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
    """
    检查文章操作权限

    Args:
        article: 文章对象
        current_user: 当前用户
        require_admin: 是否需要管理员权限

    Returns:
        (has_permission, error_message)
    """
    # 检查管理员权限
    if require_admin:
        if not hasattr(current_user, 'role') or current_user.role != 'ADMIN':
            return False, "需要管理员权限"

    # 检查作者权限
    user_id, user_type, _ = get_user_identifier(current_user)
    if not user_id:
        return False, "用户身份验证失败"

    # 管理员可以操作所有文章
    if user_type == 'admin':
        return True, None

    # 普通用户只能操作自己的文章
    if article.author_user_id != user_id:
        return False, "无权限操作此文章"

    return True, None


def build_article_query(status: Optional[str] = None, keyword: Optional[str] = None, author_id: Optional[int] = None):
    """
    构建文章查询对象

    Args:
        status: 状态筛选
        keyword: 关键词搜索
        author_id: 作者ID筛选

    Returns:
        查询对象
    """
    query = ScienceArticle.query

    # 状态筛选
    if status:
        query = query.filter(ScienceArticle.status == status)

    # 作者筛选
    if author_id:
        query = query.filter(ScienceArticle.author_user_id == author_id)

    # 关键词搜索（标题和内容）
    if keyword:
        keyword = f'%{keyword}%'
        query = query.filter(
            (ScienceArticle.title.like(keyword)) |
            (ScienceArticle.content.like(keyword))
        )

    return query