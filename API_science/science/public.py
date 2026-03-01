# 科普文章公开访问接口

from flask import Blueprint, request
from components import db
from components.models import ScienceArticle
from components.response_service import ResponseService
from components.models import User
from datetime import datetime

# 创建科普公开访问模块蓝图
bp_science_public = Blueprint('science_public', __name__, url_prefix='/api/public/science')

# 公开的科普文章列表查询（无需登录）
@bp_science_public.route('/articles', methods=['GET'])
def get_public_science_articles():
    """
    获取公开发布的科普文章列表（无需登录）
    """
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        keyword = request.args.get('keyword', '').strip()
        author_account = request.args.get('author_account', '').strip()

        # 构建查询
        query = ScienceArticle.query.filter_by(status='published')

        # 关键词搜索
        if keyword:
            query = query.filter(
                (ScienceArticle.title.like(f'%{keyword}%')) |
                (ScienceArticle.content.like(f'%{keyword}%'))
            )

        # 作者筛选
        if author_account:
            query = query.filter(ScienceArticle.author_account == author_account)

        # 分页查询
        pagination = query.order_by(ScienceArticle.published_at.desc()).paginate(page=page, per_page=size)
        articles = pagination.items
        total = pagination.total

        result_list = []
        for article in articles:
            # 获取作者基础信息
            author_info = {}
            if article.author_account:
                # 尝试从用户表获取作者信息
                author = User.query.filter_by(account=article.author_account, is_deleted=0).first()
                if author:
                    author_info = {
                        'username': author.username,
                        'avatar': author.avatar,
                        'role_cn': '普通用户'
                    }
                else:
                    # 尝试从管理员表获取
                    from components.models import Admin
                    admin = Admin.query.filter_by(account=article.author_account).first()
                    if admin:
                        author_info = {
                            'username': admin.username,
                            'avatar': admin.avatar,
                            'role_cn': '管理员'
                        }

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

# 公开的科普文章详情查询（无需登录）
@bp_science_public.route('/articles/<int:article_id>', methods=['GET'])
def get_public_science_article_detail(article_id):
    """
    获取公开发布的科普文章详情（无需登录）
    """
    try:
        article = ScienceArticle.query.filter_by(id=article_id, status='published').first()
        if not article:
            return ResponseService.error('文章不存在或未发布', status_code=404)

        # 增加浏览次数
        article.view_count += 1
        db.session.commit()

        # 获取作者信息
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
                from components.models import Admin
                admin = Admin.query.filter_by(account=article.author_account).first()
                if admin:
                    author_info = {
                        'username': admin.username,
                        'avatar': admin.avatar,
                        'role_cn': '管理员'
                    }

        # 返回完整信息
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

# 公开的科普文章统计信息（无需登录）
@bp_science_public.route('/articles/statistics', methods=['GET'])
def get_public_science_statistics():
    """
    获取科普文章公开统计信息（无需登录）
    """
    try:
        from sqlalchemy import func

        # 基本统计（仅已发布文章）
        total_published = ScienceArticle.query.filter_by(status='published').count()

        # 点赞和浏览统计
        published_stats = db.session.query(
            func.count(ScienceArticle.id).label('total_published'),
            func.sum(ScienceArticle.like_count).label('total_likes'),
            func.sum(ScienceArticle.view_count).label('total_views'),
            func.avg(ScienceArticle.like_count).label('avg_likes'),
            func.avg(ScienceArticle.view_count).label('avg_views')
        ).filter_by(status='published').first()

        # 最近发布趋势（最近30天）
        thirty_days_ago = datetime.utcnow() - datetime.timedelta(days=30)
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

print("【API_science 公开访问接口模块加载完成】")