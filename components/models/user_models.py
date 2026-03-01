# 用户管理相关模型

from datetime import datetime
from .base import BaseUser, db, get_table_comment_args


# 管理员模型（仅管理员模块使用，但定义在公共组件中供共享）
class Admin(BaseUser):
    __tablename__ = 'admin_info'
    __table_args__ = {'mysql_comment': '管理员信息表：存储系统管理员的登录信息和权限设置',
                     'comment': '管理员信息表：存储系统管理员的登录信息和权限设置'}
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='管理员记录ID（主键）')
    account = db.Column(db.String(80), unique=True, nullable=False, comment='管理员登录账号（唯一）')
    password_hash = db.Column(db.String(255), nullable=False, comment='管理员密码哈希值（加密存储）')
    username = db.Column(db.String(120), nullable=False, comment='管理员显示名称')
    phone = db.Column(db.String(20), unique=True, nullable=False, comment='管理员手机号码（唯一）')
    email = db.Column(db.String(50), comment='管理员邮箱地址')
    avatar = db.Column(db.String(200), comment='管理员头像URL地址')
    role = db.Column(db.Enum('SUPER_ADMIN', 'ADMIN'), nullable=False, default='ADMIN', comment='管理员角色（SUPER_ADMIN/ADMIN）')
    user_id = db.Column(db.Integer, db.ForeignKey('user_info.id'), nullable=False, comment='关联的用户ID（user_info表）')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, comment='管理员创建时间')
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='管理员信息更新时间')

    # 关联关系
    user = db.relationship('User', backref='admin_record', foreign_keys=[user_id])

    def sync_to_user(self, sync_password=False, force_overwrite=False):
        """将管理员信息同步到用户表（优先使用管理员表数据）"""
        if not self.user:
            raise Exception("管理员未关联用户记录")

        # 检查数据差异
        differences = self._check_data_differences()

        # 如果有差异或强制覆盖，则进行同步
        if differences or force_overwrite:
            print(f"【数据差异检测】管理员ID: {self.id}, 用户ID: {self.user_id}, 差异项: {differences}")

            # 强制使用管理员表数据进行覆盖
            self.user.account = self.account
            self.user.username = self.username
            self.user.phone = self.phone
            self.user.email = self.email
            self.user.avatar = self.avatar
            self.user.role = self.role

            # 如果需要同步密码或检测到密码差异
            if sync_password or 'password_hash' in differences:
                self.user.password_hash = self.password_hash
                print(f"【密码同步】管理员ID: {self.id}, 用户ID: {self.user_id}")

        try:
            db.session.commit()
            if differences or force_overwrite:
                print(f"【管理员信息同步到用户表】管理员ID: {self.id}, 用户ID: {self.user_id}, 覆盖字段: {differences}")
        except Exception as e:
            db.session.rollback()
            raise Exception(f"同步管理员信息到用户表失败: {str(e)}")

    def _check_data_differences(self):
        """检查管理员表和用户表的数据差异"""
        if not self.user:
            return []

        differences = []

        # 检查各个字段的差异
        if self.user.account != self.account:
            differences.append('account')
        if self.user.username != self.username:
            differences.append('username')
        if self.user.phone != self.phone:
            differences.append('phone')
        if self.user.email != self.email:
            differences.append('email')
        if self.user.avatar != self.avatar:
            differences.append('avatar')
        if self.user.role != 'ADMIN':
            differences.append('role')

        # 注意：密码哈希的差异检查需要特别处理，因为可能存在不同的哈希值对应相同密码的情况
        # 这里只检查是否两个都有值，且不相同
        if (self.user.password_hash and self.password_hash and
            self.user.password_hash != self.password_hash):
            differences.append('password_hash')

        return differences

    @classmethod
    def force_sync_all_admins(cls):
        """强制同步所有管理员数据到用户表"""
        from . import db

        admins = cls.query.all()
        synced_count = 0
        error_count = 0
        errors = []

        for admin in admins:
            try:
                admin.sync_to_user(sync_password=True, force_overwrite=True)
                synced_count += 1
                print(f"【强制同步成功】管理员ID: {admin.id}")
            except Exception as e:
                error_count += 1
                error_msg = f"管理员ID: {admin.id} 同步失败: {str(e)}"
                errors.append(error_msg)
                print(f"【强制同步失败】{error_msg}")

        return {
            'total_count': len(admins),
            'synced_count': synced_count,
            'error_count': error_count,
            'errors': errors
        }

    def demote_to_regular_user(self):
        """将管理员降级为普通用户（保留账号，只移除管理员身份）"""
        if not self.user:
            raise Exception("管理员未关联用户记录")

        try:
            # 将用户角色改为普通用户
            self.user.role = 'USER'

            # 删除管理员记录
            db.session.delete(self)
            db.session.commit()

            print(f"【管理员降级】管理员ID: {self.id} 已降级为普通用户，用户ID: {self.user_id}")
            return {
                'success': True,
                'message': '管理员已成功降级为普通用户',
                'user_id': self.user_id,
                'user_account': self.user.account
            }

        except Exception as e:
            db.session.rollback()
            raise Exception(f"管理员降级失败: {str(e)}")

    @classmethod
    def demote_admin_by_id(cls, admin_id):
        """根据管理员ID降级为普通用户"""
        admin = cls.query.get(admin_id)
        if not admin:
            raise Exception(f"未找到ID为{admin_id}的管理员")

        return admin.demote_to_regular_user()

    @classmethod
    def create_with_user(cls, admin_data, password):
        """创建管理员并同时创建用户记录"""
        from . import db

        # 准备用户数据
        user_data = {
            'account': admin_data['account'],
            'username': admin_data['username'],
            'phone': admin_data['phone'],
            'email': admin_data.get('email', ''),
            'avatar': admin_data.get('avatar', ''),
            'role': 'ADMIN',  # 用户表中标记为管理员角色
            'is_deleted': 0
        }

        try:
            # 先创建用户记录
            user = User(**user_data)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # 获取用户ID，但不提交

            # 创建管理员记录并关联用户
            admin = cls(**admin_data)
            admin.set_password(password)
            admin.user_id = user.id
            db.session.add(admin)

            db.session.commit()

            print(f"【管理员创建成功】管理员ID: {admin.id}, 用户ID: {user.id}")
            return admin

        except Exception as e:
            db.session.rollback()
            raise Exception(f"创建管理员和用户记录失败: {str(e)}")

    # 动态字段信息（供前端表格生成）
    @classmethod
    def get_fields_info(cls):
        return {
            'account': {'label': '登录账号', 'type': 'string'},
            'username': {'label': '用户名称', 'type': 'string'},
            'phone': {'label': '电话', 'type': 'string'},
            'email': {'label': '邮箱', 'type': 'string'},
            'avatar': {'label': '头像', 'type': 'string'},
            'role': {'label': '角色', 'type': 'enum', 'options': ['SUPER_ADMIN', 'ADMIN']},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True},
            'updated_at': {'label': '更新时间', 'type': 'datetime', 'readonly': True}
        }


# 新增User模型（对应user_info表）
class User(BaseUser):
    __tablename__ = 'user_info'
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='用户记录ID（主键）')
    account = db.Column(db.String(80), nullable=False, comment='用户登录账号（未注销时唯一）')
    password_hash = db.Column(db.String(255), nullable=False, comment='用户密码哈希值（加密存储）')
    username = db.Column(db.String(120), nullable=False, comment='用户显示名称')
    phone = db.Column(db.String(20), nullable=False, comment='用户手机号码（未注销时唯一）')
    email = db.Column(db.String(50), comment='用户邮箱地址')
    avatar = db.Column(db.String(200), comment='用户头像URL地址')
    role = db.Column(db.Enum('USER', 'ORG_USER', 'ADMIN', 'SUPER_ADMIN'), default='USER', comment='用户角色（USER/ORG_USER/ADMIN/SUPER_ADMIN）')
    is_deleted = db.Column(db.SmallInteger, nullable=False, default=0, comment='注销标记（0 = 正常，1 = 注销）')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, comment='用户创建时间')
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='用户信息更新时间')

    # 添加唯一索引约束（适配不同数据库）
    __table_args__ = (
        # MySQL不支持下推WHERE条件的唯一索引，改为应用层验证
        db.Index('idx_account', 'account'),
        db.Index('idx_phone', 'phone'),
        db.Index('idx_deleted', 'is_deleted'),
        # 表备注配置
        {'mysql_comment': '用户信息表：存储所有类型用户的基本信息和账号数据',
         'comment': '用户信息表：存储所有类型用户的基本信息和账号数据'},
    )

    def soft_delete(self):
        """软删除用户，将原信息保存到deleted_user表并匿名化相关数据"""
        if self.is_deleted == 1:
            return None, "用户已经注销"

        # 保存原始账号用于匿名化处理
        original_account = self.account

        # 创建注销记录
        deleted_user = DeletedUser(
            original_user_id=self.id,
            original_account=original_account,
            original_phone=self.phone
        )

        # 软删除用户
        self.is_deleted = 1
        self.account = f"deleted_{self.id}_{self.account}"  # 避免唯一约束冲突
        self.phone = f"deleted_{self.id}_{self.phone}"

        # 匿名化相关数据
        self._anonymize_activity_data(original_account)

        return deleted_user, "注销成功"

    def _anonymize_activity_data(self, original_account):
        """匿名化用户相关的活动数据"""
        from . import db
        from .activity_models import Activity, ActivityRating, ActivityDiscuss, ActivityDiscussComment

        try:
            # 1. 匿名化该用户创建的活动（使用username进行查找）
            activities_created = Activity.query.filter_by(
                organizer_user_id=self.id,
                organizer_display=self.username
            ).all()

            for activity in activities_created:
                activity.organizer_display = "用户已注销"
                activity.organizer_user_id = None

            # 2. 匿名化活动评分（使用username进行查找）
            ratings = ActivityRating.query.filter_by(
                rater_user_id=self.id,
                rater_display=self.username
            ).all()

            for rating in ratings:
                rating.update_rater_info()

            # 3. 匿名化活动讨论（使用username进行查找）
            discussions = ActivityDiscuss.query.filter_by(
                author_user_id=self.id,
                author_display=self.username
            ).all()

            for discussion in discussions:
                discussion.update_author_info()

            # 4. 匿名化讨论留言（使用username进行查找）
            discuss_comments = ActivityDiscussComment.query.filter_by(
                author_user_id=self.id,
                author_display=self.username
            ).all()

            for comment in discuss_comments:
                comment.update_author_info()

            # 5. 匿名化公告已读记录
            try:
                from .notice_models import NoticeRead
                notice_reads = NoticeRead.query.filter_by(user_id=self.id).all()

                for notice_read in notice_reads:
                    notice_read.anonymize_for_user_deletion()
            except Exception as e:
                print(f"【公告已读记录匿名化异常】用户ID: {self.id}, 错误: {str(e)}")

            db.session.commit()

        except Exception as e:
            # 记录错误但不影响注销流程
            print(f"匿名化用户活动数据时出错: {str(e)}")
            db.session.rollback()

    @classmethod
    def validate_account_unique(cls, account, exclude_user_id=None):
        """验证账号唯一性（仅针对未删除的用户）"""
        query = cls.query.filter(cls.account == account, cls.is_deleted == 0)
        if exclude_user_id:
            query = query.filter(cls.id != exclude_user_id)
        return query.first() is None

    @classmethod
    def validate_phone_unique(cls, phone, exclude_user_id=None):
        """验证手机号唯一性（仅针对未删除的用户）"""
        query = cls.query.filter(cls.phone == phone, cls.is_deleted == 0)
        if exclude_user_id:
            query = query.filter(cls.id != exclude_user_id)
        return query.first() is None

    def validate_unique_fields(self):
        """验证当前用户字段的唯一性"""
        errors = []

        if not self.validate_account_unique(self.account, exclude_user_id=self.id):
            errors.append('account')

        if not self.validate_phone_unique(self.phone, exclude_user_id=self.id):
            errors.append('phone')

        return errors

    # 字段信息（供前端表格生成，可选）
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '序号', 'type': 'int'},
            'account': {'label': '登录账号', 'type': 'string'},
            'username': {'label': '用户名称', 'type': 'string'},
            'phone': {'label': '手机号', 'type': 'string'},
            'email': {'label': '邮箱', 'type': 'string'},
            'avatar': {'label': '头像', 'type': 'string'},
            'role': {'label': '角色', 'type': 'enum', 'options': ['USER', 'ORG_USER', 'ADMIN', 'SUPER_ADMIN']},
            'is_deleted': {'label': '注销状态', 'type': 'boolean', 'options': [(0, '正常'), (1, '已注销')]},
            'created_at': {'label': '创建时间', 'type': 'datetime', 'readonly': True},
            'updated_at': {'label': '更新时间', 'type': 'datetime', 'readonly': True}
        }


# 已注销用户记录表（对应deleted_user表）
class DeletedUser(db.Model):
    __tablename__ = 'deleted_user'
    __table_args__ = {'mysql_comment': '已注销用户记录表：保存用户注销后的历史信息，支持账号和手机号的复用',
                     'comment': '已注销用户记录表：保存用户注销后的历史信息，支持账号和手机号的复用'}
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, comment='注销记录ID（主键，自增）')
    original_user_id = db.Column(db.BigInteger, nullable=False, comment='原用户ID（关联user_info表主键，用户注销后保留原ID记录）')
    original_account = db.Column(db.String(50), nullable=False, comment='原用户登录账号（注销后可复用此账号）')
    original_phone = db.Column(db.String(20), comment='原用户手机号码（注销后可复用此手机号）')
    delete_time = db.Column(db.DateTime, default=datetime.now, comment='用户注销时间（记录软删除操作的时间戳）')

    # 字段信息（供前端表格生成，可选）
    @classmethod
    def get_fields_info(cls):
        return {
            'id': {'label': '注销记录ID', 'type': 'bigint', 'readonly': True},
            'original_user_id': {'label': '原用户ID', 'type': 'bigint'},
            'original_account': {'label': '原用户账号', 'type': 'string'},
            'original_phone': {'label': '原手机号', 'type': 'string'},
            'delete_time': {'label': '注销时间', 'type': 'datetime', 'readonly': True}
        }