# API_science/science/category.py

"""
科普业务接口
包含分类管理、标签管理等功能（无用户操作相关）
"""

from flask import request, Blueprint
from components import db
from components.models import ScienceArticle
from components.response_service import ResponseService
from API_science.common.utils import format_article_data, build_article_query

# 创建科普业务蓝图
bp_science_category = Blueprint('bp_science_category', __name__)


@bp_science_category.route('/articles/popular', methods=['GET'])
def get_popular_articles():
    """获取热门科普文章（基于点赞数和浏览数）"""
    try:
        # 获取查询参数
        limit = min(int(request.args.get('limit', 10)), 50)  # 限制最大50条
        days = min(int(request.args.get('days', 30)), 365)   # 限制最大365天

        # 计算时间范围
        from datetime import datetime, timedelta
        start_date = datetime.utcnow() - timedelta(days=days)

        # 查询热门文章（已发布，按点赞数和浏览数排序）
        articles = ScienceArticle.query.filter(
            ScienceArticle.status == 'published',
            ScienceArticle.published_at >= start_date
        ).order_by(
            (ScienceArticle.like_count + ScienceArticle.view_count).desc(),
            ScienceArticle.published_at.desc()
        ).limit(limit).all()

        # 格式化文章数据
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
        # 获取查询参数
        limit = min(int(request.args.get('limit', 10)), 50)  # 限制最大50条

        # 查询最新发布的文章
        articles = ScienceArticle.query.filter(
            ScienceArticle.status == 'published'
        ).order_by(
            ScienceArticle.published_at.desc()
        ).limit(limit).all()

        # 格式化文章数据
        result_list = []
        for article in articles:
            article_data = format_article_data(article, include_content=False)
            # 添加发布时间描述
            from datetime import datetime
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
        # 获取查询参数
        limit = min(int(request.args.get('limit', 5)), 20)   # 限制最大20条
        min_likes = max(int(request.args.get('min_likes', 10)), 1)  # 最少点赞数

        # 查询精选文章（高点赞数，已发布）
        articles = ScienceArticle.query.filter(
            ScienceArticle.status == 'published',
            ScienceArticle.like_count >= min_likes
        ).order_by(
            ScienceArticle.like_count.desc(),
            ScienceArticle.published_at.desc()
        ).limit(limit).all()

        # 格式化文章数据
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
        # 获取查询参数
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

        # 构建基础查询
        query = build_article_query(status=status, keyword=keyword)

        # 点赞数筛选
        if min_likes and min_likes.isdigit():
            query = query.filter(ScienceArticle.like_count >= int(min_likes))
        if max_likes and max_likes.isdigit():
            query = query.filter(ScienceArticle.like_count <= int(max_likes))

        # 浏览数筛选
        if min_views and min_views.isdigit():
            query = query.filter(ScienceArticle.view_count >= int(min_views))
        if max_views and max_views.isdigit():
            query = query.filter(ScienceArticle.view_count <= int(max_views))

        # 日期范围筛选
        if date_from:
            try:
                from datetime import datetime
                date_from_obj = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                query = query.filter(ScienceArticle.published_at >= date_from_obj)
            except ValueError:
                return ResponseService.error('起始日期格式错误', status_code=400)

        if date_to:
            try:
                from datetime import datetime
                date_to_obj = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                query = query.filter(ScienceArticle.published_at <= date_to_obj)
            except ValueError:
                return ResponseService.error('结束日期格式错误', status_code=400)

        # 排序
        sort_field = getattr(ScienceArticle, sort_by, ScienceArticle.published_at)
        if sort_order.lower() == 'desc':
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())

        # 分页查询
        pagination = query.paginate(page=page, per_page=size, error_out=False)
        articles = pagination.items
        total = pagination.total

        # 格式化文章数据
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
def get_articles_statistics():
    """获取科普文章公开统计信息"""
    try:
        # 基本统计（仅已发布文章）
        total_published = ScienceArticle.query.filter_by(status='published').count()

        # 点赞和浏览统计
        published_stats = db.session.query(
            db.func.count(ScienceArticle.id).label('total_published'),
            db.func.sum(ScienceArticle.like_count).label('total_likes'),
            db.func.sum(ScienceArticle.view_count).label('total_views'),
            db.func.avg(ScienceArticle.like_count).label('avg_likes'),
            db.func.avg(ScienceArticle.view_count).label('avg_views')
        ).filter_by(status='published').first()

        # 各状态文章数量
        status_stats = db.session.query(
            ScienceArticle.status,
            db.func.count(ScienceArticle.id).label('count')
        ).group_by(ScienceArticle.status).all()

        status_distribution = {status: count for status, count in status_stats}

        # 最近发布趋势（最近30天）
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_stats = db.session.query(
            db.func.count(ScienceArticle.id).label('recent_published'),
            db.func.sum(ScienceArticle.like_count).label('recent_likes'),
            db.func.sum(ScienceArticle.view_count).label('recent_views')
        ).filter(
            ScienceArticle.status == 'published',
            ScienceArticle.published_at >= thirty_days_ago
        ).first()

        # 热门标签（基于标题和内容关键词）
        # 这里简化处理，可以根据需要扩展
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
        # 获取参数
        article_id = request.args.get('article_id', '').strip()
        limit = min(int(request.args.get('limit', 5)), 20)

        result_data = {
            'recommendations': [],
            'based_on': None
        }

        # 如果提供了文章ID，基于该文章推荐相似内容
        if article_id and article_id.isdigit():
            base_article = ScienceArticle.query.get(int(article_id))
            if base_article and base_article.status == 'published':
                result_data['based_on'] = {
                    'id': base_article.id,
                    'title': base_article.title
                }

                # 简单的相似度算法：基于标题关键词匹配
                # 这里简化处理，可以根据需要使用更复杂的算法
                keywords = base_article.title.split()[:3]  # 取前3个关键词作为匹配依据

                recommendations_query = ScienceArticle.query.filter(
                    ScienceArticle.status == 'published',
                    ScienceArticle.id != base_article.id
                )

                # 关键词匹配
                keyword_conditions = []
                for keyword in keywords:
                    if len(keyword) > 1:  # 跳过单字符
                        keyword_conditions.append(ScienceArticle.title.like(f'%{keyword}%'))

                if keyword_conditions:
                    from sqlalchemy import or_
                    recommendations_query = recommendations_query.filter(or_(*keyword_conditions))

                # 获取推荐文章
                recommendations = recommendations_query.order_by(
                    ScienceArticle.like_count.desc()
                ).limit(limit).all()

                result_data['recommendations'] = [
                    format_article_data(article, include_content=False)
                    for article in recommendations
                ]

        # 如果没有提供文章ID或没有找到文章，返回热门文章作为推荐
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
        # 检查数据库连接
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
                '/API_science/science/articles/popular',
                '/API_science/science/articles/latest',
                '/API_science/science/articles/featured',
                '/API_science/science/articles/search',
                '/API_science/science/articles/statistics',
                '/API_science/science/articles/recommendations',
                '/API_science/science/health'
            ]
        }

        return ResponseService.success(data=health_status, message='科普模块运行正常')

    except Exception as e:
        return ResponseService.error(f'健康检查失败：{str(e)}', status_code=500)