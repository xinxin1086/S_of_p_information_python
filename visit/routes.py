from flask import request, jsonify
from components import db
from components.models import Notice, Admin, User, Activity, ScienceArticle, ActivityBooking, ActivityRating, ActivityDiscuss, DiscussComment
from components.response_service import ResponseService, UserInfoService, format_datetime, handle_api_exception, validate_pagination_params
from datetime import datetime  # 移除 timezone 导入
from visit import visit_bp

@visit_bp.route('/notice', methods=['GET'])
def get_notices():
    try:
        notice_type = request.args.get('notice_type', '').strip()
        release_time_start = request.args.get('release_time_start', '').strip()
        release_time_end = request.args.get('release_time_end', '').strip()
        release_title = request.args.get('release_title', '').strip() or request.args.get('title', '').strip()
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))

        query = Notice.query

        if notice_type:
            query = query.filter(Notice.notice_type == notice_type)

        # 修复：直接解析 UTC 时间（与数据库存储格式一致）
        def parse_time(time_str):
            if not time_str:
                return None
            try:
                # 兼容 Z 后缀，直接解析为 UTC 时间（数据库存储格式）
                if time_str.endswith('Z'):
                    time_str = time_str.replace('Z', '+00:00')
                return datetime.fromisoformat(time_str)
            except ValueError as e:
                print(f"【时间解析失败】{time_str} -> {str(e)}")
                return None

        # 处理起始时间（直接匹配数据库的 UTC 时间）
        start_time = parse_time(release_time_start)
        if start_time:
            query = query.filter(Notice.release_time >= start_time)

        # 处理结束时间（直接匹配数据库的 UTC 时间）
        end_time = parse_time(release_time_end)
        if end_time:
            query = query.filter(Notice.release_time <= end_time)

        if release_title:
            query = query.filter(Notice.release_title.like(f'%{release_title}%'))

        pagination = query.order_by(Notice.release_time.desc()).paginate(page=page, per_page=size)
        notices = pagination.items
        total = pagination.total

        result = []
        for notice in notices:
            result.append({
                'id': notice.id,
                'release_time': notice.release_time.isoformat().replace('+00:00', 'Z'),  # 还原 Z 后缀
                'update_time': notice.update_time.isoformat().replace('+00:00', 'Z') if notice.update_time else None,
                'release_title': notice.release_title,
                # 列表页不返回公告内容，减少数据传输量
                # 'release_notice': notice.release_notice,  # 移除此字段
                'expiration': notice.expiration.isoformat().replace('+00:00', 'Z') if notice.expiration else None,
                'notice_type': notice.notice_type
            })

        return jsonify({
            'success': True,
            'message': '查询成功' if total > 0 else '无匹配数据',
            'data': {
                'total': total,
                'page': page,
                'size': size,
                'items': result
            }
        }), 200

    except Exception as e:
        print(f"【公告查询异常】{str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


@visit_bp.route('/notice/<int:notice_id>', methods=['GET'])
def get_notice_detail(notice_id):
    try:
        notice = Notice.query.get(notice_id)

        if not notice:
            return jsonify({
                'success': False,
                'message': '公告不存在',
                'data': None
            }), 404

        # 处理attachments字段（如果有）
        attachments = None
        if notice.attachments:
            try:
                import json
                attachments = json.loads(notice.attachments)
            except json.JSONDecodeError:
                attachments = None

        result = {
            'id': notice.id,
            'release_time': notice.release_time.isoformat().replace('+00:00', 'Z'),
            'update_time': notice.update_time.isoformat().replace('+00:00', 'Z') if notice.update_time else None,
            'release_title': notice.release_title,
            'release_notice': notice.release_notice,
            'expiration': notice.expiration.isoformat().replace('+00:00', 'Z') if notice.expiration else None,
            'notice_type': notice.notice_type,
            'attachments': attachments
        }

        return jsonify({
            'success': True,
            'message': '获取成功',
            'data': result
        }), 200

    except Exception as e:
        print(f"【公告详情查询异常】{str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


# 公开的用户基础信息接口（无需认证）
# 专门用于访客查看公开发布内容时的发布者信息显示
@visit_bp.route('/user/info', methods=['GET'])
@handle_api_exception
def get_public_user_info():
    """
    获取用户基础信息（公开接口，无需认证）
    专门用于访客查看公开发布内容时显示发布者信息

    必须参数：
    - account: 用户账号

    注意：此接口只返回基础信息，不包含电话、邮箱等隐私信息
    """
    try:
        # 获取用户账号参数
        account = request.args.get('account')
        if not account or not account.strip():
            return jsonify({
                'success': False,
                'message': '缺少参数：account',
                'data': None
            }), 400

        account = account.strip()
        print(f"【访客查询用户信息】查询账号: {account}")

        # 查询目标用户（支持管理员和普通用户）
        target_user = None
        user_type = None

        # 先查普通用户表
        target_user = User.query.filter_by(account=account).first()
        if target_user:
            user_type = 'user'
        else:
            # 再查管理员表
            target_user = Admin.query.filter_by(account=account).first()
            if target_user:
                user_type = 'admin'

        if not target_user:
            print(f"【访客查询失败】用户不存在: {account}")
            return jsonify({
                'success': False,
                'message': '用户不存在',
                'data': None
            }), 404

        # 返回公开的基础信息（不包含敏感信息如电话、邮箱等）
        user_info = {
            'id': target_user.id,
            'account': target_user.account,
            'username': target_user.username,
            'avatar': target_user.avatar,
            'role': target_user.role,
            'user_type': user_type  # 标识是管理员还是普通用户
        }

        # 角色中文显示
        if user_type == 'admin':
            role_mapping = {'ADMIN': '管理员', 'USER': '管理员用户'}
            user_info['role_cn'] = role_mapping.get(target_user.role, target_user.role)
        else:
            role_mapping = {'USER': '普通用户', 'ORG_USER': '组织用户'}
            user_info['role_cn'] = role_mapping.get(target_user.role, target_user.role)

        print(f"【访客查询成功】账号: {account}, 用户类型: {user_type}")
        return jsonify({
            'success': True,
            'message': '用户信息查询成功',
            'data': user_info
        }), 200

    except Exception as e:
        print(f"【访客查询用户信息异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# 访客获取活动列表接口（无需登录，包含组织者信息）
@visit_bp.route('/activities', methods=['GET'])
@handle_api_exception
@validate_pagination_params
def get_public_activities():
    """
    访客获取活动列表（无需登录）
    返回活动信息，包含组织者的基础信息
    """
    try:
        print(f"【访客活动查询请求】开始查询活动列表")

        # 获取分页和筛选参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        organizer_display = request.args.get('organizer_display')
        title = request.args.get('title')

        # 构建查询
        query = Activity.query

        # 组织者筛选
        if organizer_display:
            query = query.filter(Activity.organizer_display.like(f"%{organizer_display}%"))

        # 标题模糊搜索
        if title:
            query = query.filter(Activity.title.like(f"%{title}%"))

        # 分页查询
        pagination = query.order_by(Activity.created_at.desc()).paginate(page=page, per_page=size)
        activities = pagination.items
        total = pagination.total

        # 统计每个活动的参与人数和评分
        activity_ids = [activity.id for activity in activities]
        booking_counts = {}
        rating_stats = {}

        if activity_ids:
            from sqlalchemy import func
            # 统计预约人数
            booking_stats = db.session.query(
                ActivityBooking.activity_id,
                func.count(ActivityBooking.id).label('booking_count')
            ).filter(
                ActivityBooking.activity_id.in_(activity_ids),
                ActivityBooking.status == 'booked'
            ).group_by(ActivityBooking.activity_id).all()

            booking_counts = {stat.activity_id: stat.booking_count for stat in booking_stats}

            # 统计评分信息（平均分和评分人数）
            ratings_data = db.session.query(
                ActivityRating.activity_id,
                func.avg(ActivityRating.score).label('avg_score'),
                func.count(ActivityRating.id).label('rating_count')
            ).filter(
                ActivityRating.activity_id.in_(activity_ids)
            ).group_by(ActivityRating.activity_id).all()

            rating_stats = {
                stat.activity_id: {
                    'avg_score': round(stat.avg_score, 2) if stat.avg_score else 0,
                    'rating_count': stat.rating_count
                } for stat in ratings_data
            }

        result_list = []
        for activity in activities:
            current_participants = booking_counts.get(activity.id, 0)
            activity_rating = rating_stats.get(activity.id, {'avg_score': 0, 'rating_count': 0})

            item = {
                'id': activity.id,
                'title': activity.title,
                'location': activity.location,
                'organizer_user_id': activity.organizer_user_id,
                'organizer_display': activity.organizer_display,
                'max_participants': activity.max_participants,
                'current_participants': current_participants,
                'tags': activity.tags or [],
                'status': activity.status,
                'avg_score': activity_rating['avg_score'],
                'rating_count': activity_rating['rating_count'],
                'start_time': format_datetime(activity.start_time),
                'end_time': format_datetime(activity.end_time),
                'created_at': format_datetime(activity.created_at),
                'updated_at': format_datetime(activity.updated_at)
            }
            result_list.append(item)

        return ResponseService.paginated_success(
            items=result_list,
            total=total,
            page=page,
            size=size,
            message="活动列表查询成功"
        )

    except Exception as e:
        print(f"【访客活动查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# 访客获取活动详情接口（无需登录）
@visit_bp.route('/activities/<int:activity_id>', methods=['GET'])
@handle_api_exception
def get_public_activity_detail(activity_id):
    """
    访客获取活动详情（无需登录）
    返回完整的活动信息，包括预约人数、评分统计等
    """
    try:
        print(f"【访客活动详情查询】活动ID: {activity_id}")

        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 统计当前预约人数
        from components.models import ActivityBooking, ActivityRating
        current_bookings = ActivityBooking.query.filter_by(
            activity_id=activity.id,
            status='booked'
        ).count()

        # 获取活动评分统计
        ratings = ActivityRating.query.filter_by(activity_id=activity_id).all()
        avg_score = 0
        if ratings:
            avg_score = sum(r.score for r in ratings) / len(ratings)

        # 返回完整信息
        item = {
            'id': activity.id,
            'title': activity.title,
            'description': activity.description,
            'location': activity.location,
            'organizer_user_id': activity.organizer_user_id,
            'organizer_display': activity.organizer_display,
            'start_time': format_datetime(activity.start_time),
            'end_time': format_datetime(activity.end_time),
            'max_participants': activity.max_participants,
            'current_participants': current_bookings,
            'tags': activity.tags or [],
            'status': activity.status,
            'avg_score': round(avg_score, 2),
            'rating_count': len(ratings),
            'created_at': format_datetime(activity.created_at),
            'updated_at': format_datetime(activity.updated_at)
        }

        return ResponseService.success(data=item, message="活动详情查询成功")

    except Exception as e:
        print(f"【访客活动详情查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# 访客获取科普文章列表接口（无需登录，包含作者信息）
@visit_bp.route('/science-articles', methods=['GET'])
@handle_api_exception
@validate_pagination_params
def get_public_science_articles():
    """
    访客获取科普文章列表（无需登录）
    返回公开发布的文章信息，包含作者的基础信息
    """
    try:
        print(f"【访客科普文章查询请求】开始查询文章列表")

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
        pagination = query.order_by(ScienceArticle.published_at.desc()).paginate(page=page, per_page=size)
        articles = pagination.items
        total = pagination.total

        # 获取所有作者账号
        author_accounts = list(set([article.author_account for article in articles]))
        author_info_map = UserInfoService.get_multiple_user_info(author_accounts, include_sensitive=False)

        result_list = []
        for article in articles:
            # 获取作者信息
            author_info = author_info_map.get(article.author_account)

            item = {
                'id': article.id,
                'title': article.title,
                'summary': article.content[:200] + '...' if len(article.content) > 200 else article.content,  # 摘要
                'cover_image': article.cover_image,
                'like_count': article.like_count,
                'view_count': article.view_count,
                'published_at': format_datetime(article.published_at),
                'created_at': format_datetime(article.created_at),
                'author': {
                    'account': article.author_account,
                    'username': author_info['username'] if author_info else '未知作者',
                    'avatar': author_info['avatar'] if author_info else None,
                    'role_cn': author_info['role_cn'] if author_info else '未知角色',
                    'user_type': author_info['user_type'] if author_info else 'user'
                }
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
        print(f"【访客科普文章查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# 访客获取科普文章详情接口（无需登录，包含完整作者信息）
@visit_bp.route('/science-articles/<int:article_id>', methods=['GET'])
@handle_api_exception
def get_public_science_article_detail(article_id):
    """
    访客获取科普文章详情（无需登录）
    返回完整的文章信息和作者基础信息，同时增加浏览次数
    """
    try:
        print(f"【访客科普文章详情查询】文章ID: {article_id}")

        article = ScienceArticle.query.filter_by(id=article_id, status='published').first()
        if not article:
            return ResponseService.error('文章不存在或未发布', status_code=404)

        # 增加浏览次数
        article.view_count += 1
        from components import db
        db.session.commit()

        # 获取作者信息
        author_info = UserInfoService.get_user_by_account(article.author_account, include_sensitive=False)
        if not author_info:
            print(f"【警告】文章作者不存在: {article.author_account}")
            author_info = {
                'account': article.author_account,
                'username': '未知作者',
                'avatar': None,
                'role_cn': '未知角色',
                'user_type': 'user'
            }

        # 返回完整信息
        item = {
            'id': article.id,
            'title': article.title,
            'content': article.content,
            'cover_image': article.cover_image,
            'like_count': article.like_count,
            'view_count': article.view_count,
            'published_at': format_datetime(article.published_at),
            'created_at': format_datetime(article.created_at),
            'updated_at': format_datetime(article.updated_at),
            'author': author_info
        }

        return ResponseService.success(data=item, message="科普文章详情查询成功")

    except Exception as e:
        print(f"【访客科普文章详情查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# 访客获取活动讨论列表接口（无需登录）
@visit_bp.route('/activities/<int:activity_id>/discussions', methods=['GET'])
@handle_api_exception
def get_public_activity_discussions(activity_id):
    """
    访客获取活动讨论列表（无需登录）
    返回讨论列表，支持图片展示
    """
    try:
        print(f"【访客讨论列表查询】活动ID: {activity_id}")

        discussions = ActivityDiscuss.query.filter_by(
            activity_id=activity_id
        ).order_by(ActivityDiscuss.create_time.desc()).all()

        discussions_data = []
        for discuss in discussions:
            discussions_data.append({
                'id': discuss.id,
                'activity_id': discuss.activity_id,
                'content': discuss.content,
                'author_user_id': discuss.author_user_id,
                'author_display': discuss.author_display,
                'author_avatar': discuss.author_avatar,
                'image_urls': discuss.image_urls or [],
                'create_time': format_datetime(discuss.create_time)
            })

        return ResponseService.success(data=discussions_data, message="讨论列表查询成功")

    except Exception as e:
        print(f"【访客讨论列表查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# 访客获取活动评分详细信息接口（无需登录）
@visit_bp.route('/activities/<int:activity_id>/ratings', methods=['GET'])
@handle_api_exception
def get_public_activity_ratings(activity_id):
    """
    访客获取活动评分详细信息（无需登录）
    返回活动的评分列表，包含评分用户的基础信息
    """
    try:
        print(f"【访客评分列表查询】活动ID: {activity_id}")

        # 检查活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 获取活动的评分列表
        ratings = ActivityRating.query.filter_by(activity_id=activity_id).order_by(ActivityRating.create_time.desc()).all()

        # 获取所有评分用户的显示名
        user_displays = list(set([rating.rater_display for rating in ratings if rating.rater_display and rating.rater_display != '用户已注销']))

        # 批量获取用户信息（不包含敏感信息）
        user_info_map = {}
        if user_displays:
            user_info_map = UserInfoService.get_multiple_user_info(user_displays, include_sensitive=False)

        ratings_data = []
        for rating in ratings:
            # 获取评分用户信息
            user_info = user_info_map.get(rating.rater_display) if rating.rater_display != '用户已注销' else None

            rating_item = {
                'id': rating.id,
                'activity_id': rating.activity_id,
                'rater_display': rating.rater_display,
                'rater_avatar': rating.rater_avatar,
                'score': rating.score,
                'comment': rating.comment_content,
                'created_at': format_datetime(rating.create_time),
                'user_info': {
                    'username': user_info['username'] if user_info else '用户已注销',
                    'avatar': user_info['avatar'] if user_info else None,
                    'role_cn': user_info['role_cn'] if user_info else '已注销用户',
                    'user_type': user_info['user_type'] if user_info else 'user'
                }
            }
            ratings_data.append(rating_item)

        # 计算评分统计
        total_ratings = len(ratings)
        avg_score = 0
        if total_ratings > 0:
            avg_score = sum(rating.score for rating in ratings) / total_ratings

        result = {
            'ratings': ratings_data,
            'statistics': {
                'total_count': total_ratings,
                'average_score': round(avg_score, 2),
                'score_distribution': {}
            }
        }

        # 计算评分分布（1-5分各有多少人）
        score_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for rating in ratings:
            score_counts[rating.score] += 1

        result['statistics']['score_distribution'] = score_counts

        return ResponseService.success(data=result, message="活动评分查询成功")

    except Exception as e:
        print(f"【访客评分列表查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# 访客获取讨论留言列表接口（无需登录）
@visit_bp.route('/discussions/<int:discussion_id>/comments', methods=['GET'])
@handle_api_exception
@validate_pagination_params
def get_public_discussion_comments(discussion_id):
    """
    访客获取讨论留言列表（无需登录）
    返回讨论的留言列表，扁平结构（所有评论和回复在同一层级）
    支持分页参数：
    - page: 页码，默认1
    - size: 每页数量，默认20，最大100
    - sort: 排序方式，默认'time_asc'（时间正序），可选'time_desc'（时间倒序）
    - parent_id: 筛选特定父评论的回复，null表示主评论
    """
    try:
        print(f"【访客讨论留言列表查询】讨论ID: {discussion_id}")

        # 获取分页和筛选参数
        page = int(request.args.get('page', 1))
        size = min(int(request.args.get('size', 20)), 100)  # 限制最大每页数量
        sort = request.args.get('sort', 'time_asc')  # 默认时间正序
        parent_id = request.args.get('parent_id')  # 父评论ID筛选

        # 验证讨论是否存在
        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        # 构建查询
        query = DiscussComment.query.filter_by(discuss_id=discussion_id)

        # 父评论筛选
        if parent_id is not None:
            if parent_id.lower() == 'null':
                query = query.filter(DiscussComment.parent_comment_id.is_(None))
            else:
                try:
                    parent_id = int(parent_id)
                    query = query.filter(DiscussComment.parent_comment_id == parent_id)
                except ValueError:
                    return ResponseService.error('无效的parent_id参数', status_code=400)

        # 排序
        if sort == 'time_desc':
            query = query.order_by(DiscussComment.create_time.desc())
        else:
            query = query.order_by(DiscussComment.create_time.asc())

        # 分页查询
        pagination = query.paginate(page=page, per_page=size)
        comments = pagination.items
        total = pagination.total

        # 构建扁平结构（所有评论在同一层级）
        comments_data = []
        for comment in comments:
            comment_data = {
                'id': comment.id,
                'discuss_id': comment.discuss_id,
                'content': comment.content,
                'author_user_id': comment.author_user_id,
                'author_display': comment.author_display,
                'author_avatar': comment.author_avatar,
                'parent_comment_id': comment.parent_comment_id,
                'create_time': format_datetime(comment.create_time)
            }
            comments_data.append(comment_data)

        return ResponseService.paginated_success(
            items=comments_data,
            total=total,
            page=page,
            size=size,
            message="讨论留言列表查询成功"
        )

    except Exception as e:
        print(f"【访客讨论留言列表查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)




