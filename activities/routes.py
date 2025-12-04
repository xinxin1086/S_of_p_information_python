# ./activities/routes.py

from flask import request, jsonify
from components import token_required, db
from components.models import Activity, ActivityRating, ActivityDiscuss, DiscussComment, ActivityBooking
from components.response_service import ResponseService
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from activities import activities_bp






# 创建活动接口（需要认证）
@activities_bp.route('/', methods=['POST'])
@token_required
def create_activity(current_user):
    """
    创建新活动
    需要认证：是
    """
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        location = data.get('location', '').strip()
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        max_participants = data.get('max_participants')
        tags = data.get('tags', [])
        status = data.get('status', 'draft')

        # 验证必填字段
        if not title:
            return ResponseService.error('活动标题不能为空', status_code=400)
        if not start_time or not end_time:
            return ResponseService.error('活动时间不能为空', status_code=400)
        if not max_participants:
            return ResponseService.error('最大参与人数不能为空', status_code=400)

        # 创建活动
        activity = Activity(
            title=title,
            description=description,
            location=location,
            start_time=start_time,
            end_time=end_time,
            max_participants=int(max_participants),
            organizer_user_id=current_user.id,
            organizer_display=current_user.username,
            tags=tags if tags else [],
            status=status
        )

        db.session.add(activity)
        db.session.commit()

        print(f"【活动创建成功】活动ID: {activity.id}, 用户: {current_user.account}")

        activity_data = {
            'id': activity.id,
            'title': activity.title,
            'description': activity.description,
            'location': activity.location,
            'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'max_participants': activity.max_participants,
            'current_participants': 0,
            'tags': activity.tags or [],
            'status': activity.status,
            'organizer_display': activity.organizer_display,
            'created_at': activity.created_at.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=activity_data, message='活动创建成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'活动创建失败: {str(e)}', status_code=500)




# 活动评分接口（含评语）
@activities_bp.route('/<int:activity_id>/ratings', methods=['POST'])
@token_required
def create_activity_rating(current_user, activity_id):
    """
    发表活动评分和评语
    需要认证：是
    参数：score（1-5）, comment（可选评语）
    """
    try:
        print(f"【活动评分请求】用户: {current_user.account}, 活动ID: {activity_id}")

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        score = data.get('score')
        comment = data.get('comment', '')  # 可选评语

        # 验证评分
        if not score or not (1 <= int(score) <= 5):
            return ResponseService.error('评分必须是1-5的整数', status_code=400)

        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 检查是否已经评分过
        existing_rating = ActivityRating.query.filter_by(
            activity_id=activity_id,
            rater_user_id=current_user.id
        ).first()

        if existing_rating:
            return ResponseService.error('您已经为该活动评过分', status_code=400)

        # 创建评分
        rating = ActivityRating(
            activity_id=activity_id,
            score=int(score),
            comment_content=comment.strip() if comment else None
        )
        # 设置评分者信息（包括头像）
        rating.set_rater_info(current_user)

        db.session.add(rating)
        db.session.commit()

        print(f"【活动评分成功】评分ID: {rating.id}, 用户: {current_user.account}")

        rating_data = {
            'id': rating.id,
            'activity_id': rating.activity_id,
            'rater_user_id': rating.rater_user_id,
            'rater_display': rating.rater_display,
            'rater_avatar': rating.rater_avatar,
            'score': rating.score,
            'comment_content': rating.comment_content,
            'create_time': rating.create_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=rating_data, message='评分发表成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'评分发表失败: {str(e)}', status_code=500)




# 活动讨论创建接口（需要认证）
@activities_bp.route('/<int:activity_id>/discussions', methods=['POST'])
@token_required
def create_activity_discussion(current_user, activity_id):
    """
    创建活动讨论（需要认证）
    发起新讨论，支持图片上传
    """
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        content = data.get('content', '').strip()
        image_urls = data.get('image_urls', [])

        if not content:
            return ResponseService.error('讨论内容不能为空', status_code=400)

        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        discussion = ActivityDiscuss(
            activity_id=activity_id,
            content=content,
            image_urls=image_urls if image_urls else None
        )
        # 设置发布者信息（包括头像）
        discussion.set_author_info(current_user)

        db.session.add(discussion)
        db.session.commit()

        print(f"【活动讨论成功】讨论ID: {discussion.id}, 用户: {current_user.account}")

        discussion_data = {
            'id': discussion.id,
            'activity_id': discussion.activity_id,
            'content': discussion.content,
            'author_user_id': discussion.author_user_id,
            'author_display': discussion.author_display,
            'author_avatar': discussion.author_avatar,
            'image_urls': discussion.image_urls or [],
            'create_time': discussion.create_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=discussion_data, message='讨论发表成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'讨论发表失败: {str(e)}', status_code=500)


# 活动预约接口
@activities_bp.route('/<int:activity_id>/booking', methods=['POST', 'DELETE'])
@token_required
def activity_booking(current_user, activity_id):
    """
    活动预约接口
    POST: 预约活动
    DELETE: 取消预约
    """
    try:
        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if request.method == 'POST':
            # 预约活动
            print(f"【活动预约请求】用户: {current_user.account}, 活动ID: {activity_id}")

            # 检查是否已经预约过
            existing_booking = ActivityBooking.query.filter_by(
                activity_id=activity_id,
                user_account=current_user.account
            ).first()

            if existing_booking:
                if existing_booking.status == 'booked':
                    return ResponseService.error('您已经预约过该活动', status_code=400)
                else:
                    # 重新激活之前的预约
                    existing_booking.status = 'booked'
                    existing_booking.notes = None
                    db.session.commit()

                    print(f"【活动预约重新激活】预约ID: {existing_booking.id}, 用户: {current_user.account}")

                    booking_data = {
                        'id': existing_booking.id,
                        'activity_id': existing_booking.activity_id,
                        'user_account': existing_booking.user_account,
                        'status': existing_booking.status,
                        'booking_time': existing_booking.booking_time.isoformat().replace('+00:00', 'Z')
                    }

                    return ResponseService.success(data=booking_data, message='活动预约成功')

            # 检查活动人数限制
            if activity.max_participants:
                current_booked = ActivityBooking.query.filter_by(
                    activity_id=activity_id,
                    status='booked'
                ).count()

                if current_booked >= activity.max_participants:
                    return ResponseService.error('活动预约人数已满', status_code=400)

            # 创建新预约
            booking = ActivityBooking(
                activity_id=activity_id,
                user_account=current_user.account,
                status='booked'
            )

            db.session.add(booking)
            db.session.commit()

            print(f"【活动预约成功】预约ID: {booking.id}, 用户: {current_user.account}")

            booking_data = {
                'id': booking.id,
                'activity_id': booking.activity_id,
                'user_account': booking.user_account,
                'status': booking.status,
                'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z')
            }

            return ResponseService.success(data=booking_data, message='活动预约成功')

        else:  # DELETE - 取消预约
            print(f"【取消活动预约请求】用户: {current_user.account}, 活动ID: {activity_id}")

            booking = ActivityBooking.query.filter_by(
                activity_id=activity_id,
                user_account=current_user.account,
                status='booked'
            ).first()

            if not booking:
                return ResponseService.error('未找到有效的预约记录', status_code=404)

            booking.status = 'cancelled'
            db.session.commit()

            print(f"【活动预约取消成功】预约ID: {booking.id}, 用户: {current_user.account}")

            return ResponseService.success(data={'id': booking.id}, message='预约取消成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'预约操作失败: {str(e)}', status_code=500)


# 活动预约列表接口
@activities_bp.route('/<int:activity_id>/bookings', methods=['GET'])
@token_required
def get_activity_bookings(current_user, activity_id):
    """
    获取活动预约列表
    """
    try:
        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 获取预约列表
        bookings = ActivityBooking.query.filter_by(
            activity_id=activity_id,
            status='booked'
        ).order_by(ActivityBooking.booking_time.desc()).all()

        bookings_data = []
        for booking in bookings:
            bookings_data.append({
                'id': booking.id,
                'activity_id': booking.activity_id,
                'user_account': booking.user_account,
                'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z'),
                'status': booking.status,
                'notes': booking.notes
            })

        return ResponseService.success(data=bookings_data, message='预约列表获取成功')

    except Exception as e:
        return ResponseService.error(f'获取预约列表失败: {str(e)}', status_code=500)


# 用户预约列表接口
@activities_bp.route('/my-bookings', methods=['GET'])
@token_required
def get_my_bookings(current_user):
    """
    获取当前用户的预约列表
    """
    try:
        bookings = ActivityBooking.query.filter_by(
            user_account=current_user.account
        ).order_by(ActivityBooking.booking_time.desc()).all()

        bookings_data = []
        for booking in bookings:
            # 获取活动信息
            activity = Activity.query.get(booking.activity_id)

            bookings_data.append({
                'id': booking.id,
                'activity_id': booking.activity_id,
                'activity_title': activity.title if activity else '活动已删除',
                'activity_description': activity.description if activity else None,
                'activity_location': activity.location if activity else None,
                'activity_start_time': activity.start_time.isoformat().replace('+00:00', 'Z') if activity else None,
                'activity_end_time': activity.end_time.isoformat().replace('+00:00', 'Z') if activity else None,
                'activity_max_participants': activity.max_participants if activity else None,
                'activity_current_participants': activity.current_participants if activity else None,
                'activity_organizer_user_id': activity.organizer_user_id if activity else None,
                'activity_organizer_display': activity.organizer_display if activity else None,
                'activity_tags': activity.tags if activity else [],
                'activity_status': activity.status if activity else None,
                'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z'),
                'status': booking.status,
                'notes': booking.notes
            })

        return ResponseService.success(data=bookings_data, message='我的预约列表获取成功')

    except Exception as e:
        return ResponseService.error(f'获取我的预约列表失败: {str(e)}', status_code=500)


# 活动讨论留言接口（需要认证）
@activities_bp.route('/discussions/<int:discussion_id>/comments', methods=['POST'])
@token_required
def create_discussion_comment(current_user, discussion_id):
    """
    创建讨论留言（需要认证）
    支持嵌套回复，不可发图片
    """
    try:
        print(f"【创建讨论留言请求】讨论ID: {discussion_id}, 用户: {current_user.account}")

        # 检查数据库连接状态
        try:
            db.session.execute(text("SELECT 1"))
            print("【数据库连接】正常")
        except Exception as e:
            print(f"【数据库连接】异常: {e}")

        # 调试：检查数据库中有哪些讨论ID
        all_discussions = ActivityDiscuss.query.all()
        discussion_ids = [d.id for d in all_discussions]
        print(f"【调试】数据库中所有讨论ID: {discussion_ids}")
        print(f"【调试】找到 {len(all_discussions)} 条讨论记录")

        # 特别检查ID为8的记录
        discussion_8 = ActivityDiscuss.query.filter_by(id=8).first()
        print(f"【调试】ID为8的讨论: {discussion_8}")

        # 检查ID为8的讨论回复
        comment_8 = DiscussComment.query.filter_by(id=8).first()
        print(f"【调试】ID为8的讨论回复: {comment_8}")
        if comment_8:
            print(f"【调试】回复8所属的讨论ID: {comment_8.discuss_id}")

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        content = data.get('content', '').strip()
        parent_comment_id = data.get('parent_comment_id')  # 可选，用于回复留言

        print(f"【请求数据】content: {content}")
        print(f"【请求数据】parent_comment_id: {parent_comment_id}")

        if not content:
            return ResponseService.error('留言内容不能为空', status_code=400)

        # 如果传递的discussion_id实际上是一个comment_id，则尝试处理这种情况
        print(f"【检测】检查discussion_id {discussion_id} 是否为comment_id")
        parent_comment = DiscussComment.query.get(discussion_id)
        if parent_comment:
            print(f"【转换成功】discussion_id {discussion_id} 是comment_id")
            print(f"【父留言信息】ID: {parent_comment.id}, 讨论ID: {parent_comment.discuss_id}")
            # 重新设置参数
            discussion_id = parent_comment.discuss_id
            if not parent_comment_id:  # 如果没有明确指定parent_comment_id，则使用找到的comment
                parent_comment_id = parent_comment.id
            print(f"【修正后】discussion_id: {discussion_id}, parent_comment_id: {parent_comment_id}")
        else:
            print(f"【检测】discussion_id {discussion_id} 不是comment_id，继续作为discussion_id处理")

        # 验证讨论是否存在
        print(f"【查找讨论】讨论ID: {discussion_id}")

        # 尝试多种查询方式
        discussion = ActivityDiscuss.query.get(discussion_id)
        print(f"【方法1- query.get】查询结果: {discussion}")

        if not discussion:
            # 尝试使用filter_by方式查询
            discussion = ActivityDiscuss.query.filter_by(id=discussion_id).first()
            print(f"【方法2- filter_by】查询结果: {discussion}")

        if not discussion:
            # 尝试原始SQL查询
            sql_result = db.session.execute(text("SELECT * FROM activity_discuss WHERE id = :id"), {"id": discussion_id}).fetchone()
            print(f"【方法3- 原始SQL】查询结果: {sql_result}")

            # 如果还是没有找到，列出所有可用的讨论ID供调试
            all_discussions = ActivityDiscuss.query.all()
            print(f"【所有可用讨论】")
            for d in all_discussions:
                print(f"  - ID: {d.id}, 内容: {d.content[:50]}...")

            return ResponseService.error(f'讨论不存在，ID: {discussion_id}', status_code=404)

        # 如果是回复留言，验证父留言是否存在
        if parent_comment_id:
            parent_comment = DiscussComment.query.get(parent_comment_id)
            if not parent_comment or parent_comment.discuss_id != discussion_id:
                return ResponseService.error('父留言不存在或不属于该讨论', status_code=404)

        # 创建留言
        comment = DiscussComment(
            discuss_id=discussion_id,
            content=content,
            parent_comment_id=parent_comment_id if parent_comment_id else None
        )
        # 设置发布者信息（包括头像）
        comment.set_author_info(current_user)

        db.session.add(comment)
        db.session.commit()

        print(f"【讨论留言成功】留言ID: {comment.id}, 用户: {current_user.account}")

        comment_data = {
            'id': comment.id,
            'discuss_id': comment.discuss_id,
            'content': comment.content,
            'author_user_id': comment.author_user_id,
            'author_display': comment.author_display,
            'author_avatar': comment.author_avatar,
            'parent_comment_id': comment.parent_comment_id,
            'create_time': comment.create_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=comment_data, message='留言发表成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'留言发表失败: {str(e)}', status_code=500)


# 获取讨论留言列表接口（需要认证）
@activities_bp.route('/discussions/<int:discussion_id>/comments', methods=['GET'])
@token_required
def get_discussion_comments(current_user, discussion_id):
    """
    获取讨论留言列表（需要认证）
    返回讨论的留言列表，支持嵌套结构
    """
    try:
        print(f"【讨论留言列表查询】讨论ID: {discussion_id}")

        # 验证讨论是否存在
        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        # 获取所有留言，按时间正序排列（便于构建嵌套结构）
        comments = DiscussComment.query.filter_by(
            discuss_id=discussion_id
        ).order_by(DiscussComment.create_time.asc()).all()

        # 构建嵌套结构
        comments_dict = {}
        root_comments = []

        for comment in comments:
            comment_data = {
                'id': comment.id,
                'discuss_id': comment.discuss_id,
                'content': comment.content,
                'author_user_id': comment.author_user_id,
                'author_display': comment.author_display,
                'author_avatar': comment.author_avatar,
                'parent_comment_id': comment.parent_comment_id,
                'create_time': comment.create_time.isoformat().replace('+00:00', 'Z'),
                'replies': []
            }
            comments_dict[comment.id] = comment_data

            if comment.parent_comment_id is None:
                root_comments.append(comment_data)
            else:
                if comment.parent_comment_id in comments_dict:
                    comments_dict[comment.parent_comment_id]['replies'].append(comment_data)

        return ResponseService.success(data=root_comments, message="留言列表查询成功")

    except Exception as e:
        print(f"【讨论留言列表查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# 删除讨论留言接口（需要认证）- 实现层级删除逻辑
@activities_bp.route('/discussions/comments/<int:comment_id>', methods=['DELETE'])
@token_required
def delete_discussion_comment(current_user, comment_id):
    """
    删除讨论留言（需要认证）
    实现层级删除逻辑：
    - 删除留言时，其子留言的parent_comment_id设为NULL，保留子留言
    - 只能删除自己发布的留言
    """
    try:
        print(f"【删除讨论留言请求】留言ID: {comment_id}, 用户: {current_user.account}")

        comment = DiscussComment.query.get(comment_id)
        if not comment:
            return ResponseService.error('留言不存在', status_code=404)

        # 验证是否为留言作者
        if comment.author_user_id != current_user.id:
            return ResponseService.error('无权删除此留言', status_code=403)

        # 层级删除逻辑：将子留言的parent_comment_id设为NULL
        child_comments = DiscussComment.query.filter_by(parent_comment_id=comment_id).all()
        for child_comment in child_comments:
            child_comment.parent_comment_id = None
            print(f"【子留言处理】子留言ID: {child_comment.id} 的parent_comment_id设为NULL")

        # 删除目标留言
        db.session.delete(comment)
        db.session.commit()

        print(f"【讨论留言删除成功】留言ID: {comment_id}, 用户: {current_user.account}")
        print(f"【子留言保留】共保留 {len(child_comments)} 条子留言")

        return ResponseService.success(
            data={
                'id': comment_id,
                'preserved_child_count': len(child_comments)
            },
            message='留言删除成功，子留言已保留'
        )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'留言删除失败: {str(e)}', status_code=500)


# 删除活动讨论接口（需要认证）- 删除讨论及其所有留言
@activities_bp.route('/discussions/<int:discussion_id>', methods=['DELETE'])
@token_required
def delete_activity_discussion(current_user, discussion_id):
    """
    删除活动讨论（需要认证）
    删除讨论及其所有相关留言（级联删除）
    只能删除自己发布的讨论
    """
    try:
        print(f"【删除活动讨论请求】讨论ID: {discussion_id}, 用户: {current_user.account}")

        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        # 验证是否为讨论作者
        if discussion.author_user_id != current_user.id:
            return ResponseService.error('无权删除此讨论', status_code=403)

        # 统计即将删除的留言数量
        comment_count = DiscussComment.query.filter_by(discuss_id=discussion_id).count()

        # 删除讨论（由于外键约束ondelete='CASCADE'，所有相关留言会自动删除）
        db.session.delete(discussion)
        db.session.commit()

        print(f"【活动讨论删除成功】讨论ID: {discussion_id}, 用户: {current_user.account}")
        print(f"【级联删除留言】共删除 {comment_count} 条相关留言")

        return ResponseService.success(
            data={
                'id': discussion_id,
                'deleted_comment_count': comment_count
            },
            message='讨论删除成功，所有相关留言已删除'
        )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'讨论删除失败: {str(e)}', status_code=500)