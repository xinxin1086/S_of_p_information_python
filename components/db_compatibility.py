# 数据库兼容性工具
"""
处理SQLite和MySQL数据库之间的兼容性问题
提供统一的接口来处理不同数据库的方言差异
"""

from flask import current_app
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def get_database_type():
    """获取当前使用的数据库类型"""
    try:
        database_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if 'sqlite' in database_uri.lower():
            return 'sqlite'
        elif 'mysql' in database_uri.lower():
            return 'mysql'
        elif 'postgresql' in database_uri.lower():
            return 'postgresql'
        else:
            return 'unknown'
    except Exception:
        return 'unknown'


def enable_foreign_keys(db_engine):
    """为数据库启用外键约束"""
    db_type = get_database_type()

    try:
        if db_type == 'sqlite':
            # SQLite需要显式启用外键约束
            connection = db_engine.connect()
            connection.execute(text("PRAGMA foreign_keys = ON"))
            connection.close()
            logger.info("SQLite外键约束已启用")
        elif db_type == 'mysql':
            # MySQL默认支持外键约束，但可以检查是否已启用
            connection = db_engine.connect()
            result = connection.execute(text("SHOW VARIABLES LIKE 'foreign_key_checks'"))
            row = result.fetchone()
            connection.close()
            if row and row[1] == 'OFF':
                logger.warning("MySQL外键约束未启用，可能导致数据完整性问题")
            else:
                logger.info("MySQL外键约束状态正常")
        # PostgreSQL默认支持外键约束
    except Exception as e:
        logger.warning(f"启用外键约束时发生错误: {str(e)}")


def get_compatible_index_definition(table_name, columns, unique=False, condition=None):
    """
    获取兼容不同数据库的索引定义

    Args:
        table_name: 表名
        columns: 列名列表
        unique: 是否唯一索引
        condition: 索引条件（仅适用于支持的条件索引）

    Returns:
        dict: SQLAlchemy兼容的索引配置
    """
    from . import db

    db_type = get_database_type()

    if unique and condition and db_type == 'mysql':
        # MySQL不支持条件索引，改为普通唯一索引
        # 实际的唯一性需要在应用层验证
        index_name = f"idx_{table_name}_{'_'.join(columns)}"
        return {
            'name': index_name,
            'columns': columns,
            'unique': False  # 改为普通索引，应用层验证唯一性
        }
    elif unique and condition and db_type in ['sqlite', 'postgresql']:
        # SQLite和PostgreSQL支持条件索引
        index_name = f"idx_{table_name}_{'_'.join(columns)}_unique"
        return {
            'name': index_name,
            'columns': columns,
            'unique': True,
            'postgresql_where': condition,
            'sqlite_where': condition
        }
    else:
        # 普通索引
        index_name = f"idx_{table_name}_{'_'.join(columns)}"
        return {
            'name': index_name,
            'columns': columns,
            'unique': unique
        }


def get_compatible_autoincrement_field():
    """获取兼容不同数据库的自增字段定义"""
    db_type = get_database_type()

    if db_type == 'sqlite':
        # SQLite只支持INTEGER自增
        return {'type': 'Integer', 'autoincrement': True}
    else:
        # MySQL和PostgreSQL支持更多类型
        return {'type': 'Integer', 'autoincrement': True}


def validate_connection_health(db_engine):
    """验证数据库连接健康状态"""
    try:
        connection = db_engine.connect()
        connection.execute(text("SELECT 1"))
        connection.close()
        return True
    except Exception as e:
        logger.error(f"数据库连接健康检查失败: {str(e)}")
        return False


def get_database_info(db_engine):
    """获取数据库信息"""
    db_type = get_database_type()

    try:
        connection = db_engine.connect()

        if db_type == 'sqlite':
            result = connection.execute(text("SELECT sqlite_version()"))
            version = result.fetchone()[0]
            info = {
                'type': 'SQLite',
                'version': version,
                'features': ['foreign_keys', 'transactions', 'acid']
            }
        elif db_type == 'mysql':
            result = connection.execute(text("SELECT VERSION()"))
            version = result.fetchone()[0]
            info = {
                'type': 'MySQL',
                'version': version,
                'features': ['foreign_keys', 'transactions', 'acid', 'complex_indexes']
            }
        elif db_type == 'postgresql':
            result = connection.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            info = {
                'type': 'PostgreSQL',
                'version': version,
                'features': ['foreign_keys', 'transactions', 'acid', 'complex_indexes', 'jsonb']
            }
        else:
            info = {
                'type': 'Unknown',
                'version': 'Unknown',
                'features': []
            }

        connection.close()
        return info

    except Exception as e:
        logger.error(f"获取数据库信息失败: {str(e)}")
        return {
            'type': db_type,
            'version': 'Unknown',
            'features': [],
            'error': str(e)
        }


class DatabaseCompatibilityManager:
    """数据库兼容性管理器"""

    def __init__(self, db_engine=None):
        self.db_engine = db_engine
        self.db_type = get_database_type()

    def setup_database_compatibility(self):
        """设置数据库兼容性配置"""
        if not self.db_engine:
            logger.error("数据库引擎未初始化")
            return False

        try:
            # 启用外键约束
            self.enable_foreign_keys()

            # 执行数据库特定的初始化
            self._initialize_database_specifics()

            logger.info(f"数据库兼容性配置完成: {self.db_type}")
            return True

        except Exception as e:
            logger.error(f"数据库兼容性配置失败: {str(e)}")
            return False

    def enable_foreign_keys(self):
        """启用外键约束"""
        enable_foreign_keys(self.db_engine)

    def _initialize_database_specifics(self):
        """执行数据库特定的初始化"""
        connection = self.db_engine.connect()

        try:
            if self.db_type == 'sqlite':
                # SQLite特定配置
                connection.execute(text("PRAGMA journal_mode = WAL"))
                connection.execute(text("PRAGMA synchronous = NORMAL"))
                connection.execute(text("PRAGMA cache_size = 1000"))
                logger.info("SQLite性能优化配置已应用")

            elif self.db_type == 'mysql':
                # MySQL特定配置
                connection.execute(text("SET sql_mode = 'STRICT_TRANS_TABLES'"))
                logger.info("MySQL严格模式已启用")

        except Exception as e:
            logger.warning(f"数据库特定配置应用失败: {str(e)}")
        finally:
            connection.close()

    def get_compatibility_status(self):
        """获取兼容性状态"""
        info = get_database_info(self.db_engine)
        info['health'] = validate_connection_health(self.db_engine)
        info['type'] = self.db_type
        return info