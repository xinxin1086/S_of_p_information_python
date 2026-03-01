# 数据模型基础文件

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# 初始化数据库（所有模块共享）
db = SQLAlchemy()

# 为Flask-SQLAlchemy 3.x兼容性修复
class FlaskSQLAlchemyCompatibility:
    """修复Flask-SQLAlchemy 3.x版本兼容性问题"""

    @staticmethod
    def get_session():
        """获取数据库会话，兼容不同版本"""
        try:
            # Flask-SQLAlchemy 3.x
            return db.session
        except TypeError:
            # 旧版本
            return db.session()

# 创建兼容性会话获取器
compat_session = FlaskSQLAlchemyCompatibility.get_session


def get_table_comment_args(comment):
    """
    根据数据库类型生成表备注配置

    Args:
        comment (str): 表备注内容

    Returns:
        dict: 包含表备注配置的字典
    """
    try:
        # 获取当前数据库引擎的URL
        engine_url = str(db.engine.url).lower()

        if 'mysql' in engine_url:
            return {'mysql_comment': comment}
        elif 'postgresql' in engine_url:
            return {'comment': comment}
        elif 'sqlite' in engine_url:
            # SQLite 不支持表备注，返回空配置
            return {}
        else:
            # 默认情况，尝试使用通用配置
            return {'comment': comment}
    except:
        # 如果无法获取数据库信息，返回空配置
        return {}


# 基类模型，包含密码加密与验证的方法
class BaseUser(db.Model):
    """用户基础模型，提供密码哈希和验证功能"""
    __abstract__ = True

    def set_password(self, password):
        """设置用户密码（哈希加密存储）"""
        if not isinstance(password, str) or not password:
            raise ValueError('密码必须是非空字符串')
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证用户密码"""
        if not isinstance(password, str) or not password:
            raise ValueError('密码必须是非空字符串')
        return check_password_hash(self.password_hash, password)