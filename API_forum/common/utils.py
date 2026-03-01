
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from flask import request
from components.models.forum_models import ForumPost, ForumFloor, ForumReply
from components import db


class SensitiveWordFilter:
    

    def __init__(self, sensitive_words: List[str] = None):
        
        self.sensitive_words = sensitive_words or [
            '违禁词1', '违禁词2', '违禁词3',
            '垃圾信息', '广告', '违法', '暴力', '色情'
        ]
        self.pattern = re.compile('|'.join(map(re.escape, self.sensitive_words)), re.IGNORECASE)

    def filter_content(self, content: str) -> str:
        
        if not content:
            return content

        filtered_content = self.pattern.sub('***', content)
        return filtered_content

    def contains_sensitive_word(self, content: str) -> bool:
        
        if not content:
            return False

        return bool(self.pattern.search(content))

    def get_sensitive_words(self, content: str) -> List[str]:
        
        if not content:
            return []

        return list(set(match.group() for match in self.pattern.finditer(content)))


class PostSorter:
    

    @staticmethod
    def sort_posts(posts: List[ForumPost], sort_by: str = 'latest') -> List[ForumPost]:
        
        if sort_by == 'latest':
            return sorted(posts, key=lambda x: x.created_at, reverse=True)
        elif sort_by == 'hottest':
            return sorted(posts, key=lambda x: x.calculate_like_count() + x.calculate_comment_count() + x.view_count/10, reverse=True)
        elif sort_by == 'most_viewed':
            return sorted(posts, key=lambda x: x.view_count, reverse=True)
        elif sort_by == 'most_liked':
            return sorted(posts, key=lambda x: x.calculate_like_count(), reverse=True)
        else:
            return sorted(posts, key=lambda x: x.created_at, reverse=True)

    @staticmethod
    def get_hot_posts(hours: int = 24, limit: int = 10) -> List[ForumPost]:
        
        from datetime import timedelta

        time_threshold = datetime.now() - timedelta(hours=hours)

        recent_posts = ForumPost.query.filter(
            ForumPost.created_at >= time_threshold,
            ForumPost.status == 'published'
        ).all()

        hot_posts = PostSorter.sort_posts(recent_posts, 'hottest')

        return hot_posts[:limit]


class PaginationHelper:
    

    @staticmethod
    def get_pagination_params() -> Dict[str, int]:
        
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('size', 20)), 100)

        page = max(page, 1)

        return {'page': page, 'per_page': per_page}

    @staticmethod
    def format_pagination_response(pagination, items: List[Any], transform_func=None) -> Dict[str, Any]:
        
        if transform_func:
            formatted_items = [transform_func(item) for item in items]
        else:
            formatted_items = items

        return {
            'total': pagination.total,
            'page': pagination.page,
            'size': pagination.per_page,
            'pages': pagination.pages,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'items': formatted_items
        }


class PermissionHelper:
    

    @staticmethod
    def can_edit_post(user, post) -> bool:
        
        if hasattr(user, 'role') and user.role in ['ADMIN', 'SUPER_ADMIN']:
            return True

        if hasattr(user, 'is_deleted'):
            return post.author_user_id == user.id
        elif hasattr(user, 'role'):
            return post.author_user_id == user.id

        return False

    @staticmethod
    def can_delete_post(user, post) -> bool:
        
        if hasattr(user, 'role') and user.role in ['ADMIN', 'SUPER_ADMIN']:
            return True

        if hasattr(user, 'is_deleted'):
            return post.author_user_id == user.id
        elif hasattr(user, 'role'):
            return post.author_user_id == user.id

        return False

    @staticmethod
    def can_edit_floor(user, floor) -> bool:
        
        if hasattr(user, 'role') and user.role in ['ADMIN', 'SUPER_ADMIN']:
            return True

        if hasattr(user, 'is_deleted'):
            return floor.author_user_id == user.id
        elif hasattr(user, 'role'):
            return floor.author_user_id == user.id

        return False

    @staticmethod
    def can_edit_reply(user, reply) -> bool:
        
        if hasattr(user, 'role') and user.role in ['ADMIN', 'SUPER_ADMIN']:
            return True

        if hasattr(user, 'is_deleted'):
            return reply.author_user_id == user.id
        elif hasattr(user, 'role'):
            return reply.author_user_id == user.id

        return False


class ForumStatsHelper:
    

    @staticmethod
    def get_post_stats(days: int = 7) -> Dict[str, int]:
        
        from datetime import timedelta

        time_threshold = datetime.now() - timedelta(days=days)

        total_posts = ForumPost.query.count()
        recent_posts = ForumPost.query.filter(
            ForumPost.created_at >= time_threshold
        ).count()
        published_posts = ForumPost.query.filter_by(status='published').count()

        return {
            'total': total_posts,
            'recent': recent_posts,
            'published': published_posts,
            'draft': total_posts - published_posts
        }

    @staticmethod
    def get_user_participation_stats(user_id: int, days: int = 30) -> Dict[str, int]:
        
        from datetime import timedelta

        time_threshold = datetime.now() - timedelta(days=days)

        posts_count = ForumPost.query.filter(
            ForumPost.author_user_id == user_id,
            ForumPost.created_at >= time_threshold
        ).count()

        floors_count = ForumFloor.query.filter(
            ForumFloor.author_user_id == user_id,
            ForumFloor.created_at >= time_threshold
        ).count()

        replies_count = ForumReply.query.filter(
            ForumReply.author_user_id == user_id,
            ForumReply.created_at >= time_threshold
        ).count()

        return {
            'posts': posts_count,
            'floors': floors_count,
            'replies': replies_count,
            'total': posts_count + floors_count + replies_count
        }


sensitive_filter = SensitiveWordFilter()
post_sorter = PostSorter()


def validate_content(content: str, min_length: int = 1, max_length: int = 10000) -> Dict[str, Any]:
    
    if not content or len(content.strip()) < min_length:
        return {'valid': False, 'message': f'内容不能少于{min_length}个字符'}

    if len(content) > max_length:
        return {'valid': False, 'message': f'内容不能超过{max_length}个字符'}

    if sensitive_filter.contains_sensitive_word(content):
        found_words = sensitive_filter.get_sensitive_words(content)
        return {'valid': False, 'message': f'内容包含敏感词：{", ".join(found_words)}'}

    return {'valid': True, 'message': '内容验证通过'}


def create_nested_reply_structure(replies: List[ForumReply]) -> List[Dict[str, Any]]:
    
    result = []

    for reply in replies:
        reply_data = {
            'id': reply.id,
            'content': reply.content,
            'author_display': reply.author_display,
            'like_count': reply.calculate_like_count(),
            'quote_content': reply.quote_content,
            'quote_author': reply.quote_author,
            'created_at': reply.created_at.isoformat() if reply.created_at else None,
            'updated_at': reply.updated_at.isoformat() if reply.updated_at else None
        }
        result.append(reply_data)

    return result