# API_forum 公共工具模块

import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from flask import request
from components.models.forum_models import ForumPost, ForumFloor, ForumReply
from components import db


class SensitiveWordFilter:
    """敏感词过滤工具类"""

    def __init__(self, sensitive_words: List[str] = None):
        """
        初始化敏感词过滤器

        Args:
            sensitive_words: 敏感词列表，如果为空则使用默认敏感词库
        """
        self.sensitive_words = sensitive_words or [
            '违禁词1', '违禁词2', '违禁词3',  # 实际项目中应从配置或数据库加载
            '垃圾信息', '广告', '违法', '暴力', '色情'
        ]
        self.pattern = re.compile('|'.join(map(re.escape, self.sensitive_words)), re.IGNORECASE)

    def filter_content(self, content: str) -> str:
        """
        过滤内容中的敏感词

        Args:
            content: 待过滤的内容

        Returns:
            过滤后的内容
        """
        if not content:
            return content

        # 将敏感词替换为 ***
        filtered_content = self.pattern.sub('***', content)
        return filtered_content

    def contains_sensitive_word(self, content: str) -> bool:
        """
        检查内容是否包含敏感词

        Args:
            content: 待检查的内容

        Returns:
            是否包含敏感词
        """
        if not content:
            return False

        return bool(self.pattern.search(content))

    def get_sensitive_words(self, content: str) -> List[str]:
        """
        获取内容中的敏感词列表

        Args:
            content: 待检查的内容

        Returns:
            找到的敏感词列表
        """
        if not content:
            return []

        return list(set(match.group() for match in self.pattern.finditer(content)))


class PostSorter:
    """帖子排序工具类"""

    @staticmethod
    def sort_posts(posts: List[ForumPost], sort_by: str = 'latest') -> List[ForumPost]:
        """
        根据指定方式排序帖子

        Args:
            posts: 帖子列表
            sort_by: 排序方式 ('latest', 'hottest', 'most_viewed', 'most_liked')

        Returns:
            排序后的帖子列表
        """
        if sort_by == 'latest':
            # 按创建时间倒序
            return sorted(posts, key=lambda x: x.created_at, reverse=True)
        elif sort_by == 'hottest':
            # 按热度计算（点赞数 + 评论数 + 浏览数/10）
            return sorted(posts, key=lambda x: x.calculate_like_count() + x.calculate_comment_count() + x.view_count/10, reverse=True)
        elif sort_by == 'most_viewed':
            # 按浏览量倒序
            return sorted(posts, key=lambda x: x.view_count, reverse=True)
        elif sort_by == 'most_liked':
            # 按点赞数倒序
            return sorted(posts, key=lambda x: x.calculate_like_count(), reverse=True)
        else:
            # 默认按创建时间倒序
            return sorted(posts, key=lambda x: x.created_at, reverse=True)

    @staticmethod
    def get_hot_posts(hours: int = 24, limit: int = 10) -> List[ForumPost]:
        """
        获取热门帖子

        Args:
            hours: 多少小时内的热门帖子
            limit: 返回数量限制

        Returns:
            热门帖子列表
        """
        from datetime import timedelta

        # 计算时间范围
        time_threshold = datetime.now() - timedelta(hours=hours)

        # 查询指定时间内的帖子
        recent_posts = ForumPost.query.filter(
            ForumPost.created_at >= time_threshold,
            ForumPost.status == 'published'
        ).all()

        # 按热度排序
        hot_posts = PostSorter.sort_posts(recent_posts, 'hottest')

        return hot_posts[:limit]


class PaginationHelper:
    """分页辅助工具类"""

    @staticmethod
    def get_pagination_params() -> Dict[str, int]:
        """
        从请求中获取分页参数

        Returns:
            包含page和per_page的字典
        """
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('size', 20)), 100)  # 限制最大每页数量

        # 确保页码至少为1
        page = max(page, 1)

        return {'page': page, 'per_page': per_page}

    @staticmethod
    def format_pagination_response(pagination, items: List[Any], transform_func=None) -> Dict[str, Any]:
        """
        格式化分页响应

        Args:
            pagination: 分页对象
            items: 数据项列表
            transform_func: 转换函数，用于处理每个item

        Returns:
            格式化的分页响应数据
        """
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
    """权限检查辅助工具类"""

    @staticmethod
    def can_edit_post(user, post) -> bool:
        """
        检查用户是否可以编辑帖子

        Args:
            user: 当前用户对象
            post: 帖子对象

        Returns:
            是否有编辑权限
        """
        # 管理员可以编辑所有帖子
        if hasattr(user, 'role') and user.role in ['ADMIN', 'SUPER_ADMIN']:
            return True

        # 帖子作者可以编辑
        if hasattr(user, 'is_deleted'):  # 普通用户
            return post.author_user_id == user.id
        elif hasattr(user, 'role'):  # 管理员用户
            return post.author_user_id == user.id

        return False

    @staticmethod
    def can_delete_post(user, post) -> bool:
        """
        检查用户是否可以删除帖子

        Args:
            user: 当前用户对象
            post: 帖子对象

        Returns:
            是否有删除权限
        """
        # 管理员可以删除所有帖子
        if hasattr(user, 'role') and user.role in ['ADMIN', 'SUPER_ADMIN']:
            return True

        # 帖子作者可以删除
        if hasattr(user, 'is_deleted'):  # 普通用户
            return post.author_user_id == user.id
        elif hasattr(user, 'role'):  # 管理员用户
            return post.author_user_id == user.id

        return False

    @staticmethod
    def can_edit_floor(user, floor) -> bool:
        """
        检查用户是否可以编辑楼层

        Args:
            user: 当前用户对象
            floor: 楼层对象

        Returns:
            是否有编辑权限
        """
        # 管理员可以编辑所有楼层
        if hasattr(user, 'role') and user.role in ['ADMIN', 'SUPER_ADMIN']:
            return True

        # 楼层作者可以编辑
        if hasattr(user, 'is_deleted'):  # 普通用户
            return floor.author_user_id == user.id
        elif hasattr(user, 'role'):  # 管理员用户
            return floor.author_user_id == user.id

        return False

    @staticmethod
    def can_edit_reply(user, reply) -> bool:
        """
        检查用户是否可以编辑回复

        Args:
            user: 当前用户对象
            reply: 回复对象

        Returns:
            是否有编辑权限
        """
        # 管理员可以编辑所有回复
        if hasattr(user, 'role') and user.role in ['ADMIN', 'SUPER_ADMIN']:
            return True

        # 回复作者可以编辑
        if hasattr(user, 'is_deleted'):  # 普通用户
            return reply.author_user_id == user.id
        elif hasattr(user, 'role'):  # 管理员用户
            return reply.author_user_id == user.id

        return False


class ForumStatsHelper:
    """论坛统计辅助工具类"""

    @staticmethod
    def get_post_stats(days: int = 7) -> Dict[str, int]:
        """
        获取帖子统计信息

        Args:
            days: 统计天数

        Returns:
            统计信息字典
        """
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
        """
        获取用户参与统计

        Args:
            user_id: 用户ID
            days: 统计天数

        Returns:
            用户参与统计信息
        """
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


# 全局实例
sensitive_filter = SensitiveWordFilter()
post_sorter = PostSorter()


def validate_content(content: str, min_length: int = 1, max_length: int = 10000) -> Dict[str, Any]:
    """
    验证内容

    Args:
        content: 待验证内容
        min_length: 最小长度
        max_length: 最大长度

    Returns:
        验证结果 {'valid': bool, 'message': str}
    """
    if not content or len(content.strip()) < min_length:
        return {'valid': False, 'message': f'内容不能少于{min_length}个字符'}

    if len(content) > max_length:
        return {'valid': False, 'message': f'内容不能超过{max_length}个字符'}

    if sensitive_filter.contains_sensitive_word(content):
        found_words = sensitive_filter.get_sensitive_words(content)
        return {'valid': False, 'message': f'内容包含敏感词：{", ".join(found_words)}'}

    return {'valid': True, 'message': '内容验证通过'}


def create_nested_reply_structure(replies: List[ForumReply]) -> List[Dict[str, Any]]:
    """
    创建嵌套回复结构

    Args:
        replies: 回复列表

    Returns:
        嵌套结构的回复列表
    """
    # 这里可以实现更复杂的嵌套逻辑
    # 当前只是简单的平铺结构，可以根据需要扩展
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