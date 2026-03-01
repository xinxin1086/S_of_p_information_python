

from flask import current_app
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def get_database_type():
    
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
    
    db_type = get_database_type()

    try:
        if db_type == 'sqlite':
            connection = db_engine.connect()
            connection.execute(text("PRAGMA foreign_keys = ON"))
            connection.close()
            logger.info("SQLite外键约束已启用")
        elif db_type == 'mysql':
            connection = db_engine.connect()
            result = connection.execute(text("SHOW VARIABLES LIKE 'foreign_key_checks'"))
            row = result.fetchone()
            connection.close()
            if row and row[1] == 'OFF':
                logger.warning("MySQL外键约束未启用，可能导致数据完整性问题")
            else:
                logger.info("MySQL外键约束状态正常")
    except Exception as e:
        logger.warning(f"启用外键约束时发生错误: {str(e)}")


def get_compatible_index_definition(table_name, columns, unique=False, condition=None):
    
    from . import db

    db_type = get_database_type()

    if unique and condition and db_type == 'mysql':
        index_name = f"idx_{table_name}_{'_'.join(columns)}"
        return {
            'name': index_name,
            'columns': columns,
            'unique': False
        }
    elif unique and condition and db_type in ['sqlite', 'postgresql']:
        index_name = f"idx_{table_name}_{'_'.join(columns)}_unique"
        return {
            'name': index_name,
            'columns': columns,
            'unique': True,
            'postgresql_where': condition,
            'sqlite_where': condition
        }
    else:
        index_name = f"idx_{table_name}_{'_'.join(columns)}"
        return {
            'name': index_name,
            'columns': columns,
            'unique': unique
        }


def get_compatible_autoincrement_field():
    
    db_type = get_database_type()

    if db_type == 'sqlite':
        return {'type': 'Integer', 'autoincrement': True}
    else:
        return {'type': 'Integer', 'autoincrement': True}


def validate_connection_health(db_engine):
    
    try:
        connection = db_engine.connect()
        connection.execute(text("SELECT 1"))
        connection.close()
        return True
    except Exception as e:
        logger.error(f"数据库连接健康检查失败: {str(e)}")
        return False


def get_database_info(db_engine):
    
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
    

    def __init__(self, db_engine=None):
        self.db_engine = db_engine
        self.db_type = get_database_type()

    def setup_database_compatibility(self):
        
        if not self.db_engine:
            logger.error("数据库引擎未初始化")
            return False

        try:
            self.enable_foreign_keys()

            self._initialize_database_specifics()

            logger.info(f"数据库兼容性配置完成: {self.db_type}")
            return True

        except Exception as e:
            logger.error(f"数据库兼容性配置失败: {str(e)}")
            return False

    def enable_foreign_keys(self):
        
        enable_foreign_keys(self.db_engine)

    def _initialize_database_specifics(self):
        
        connection = self.db_engine.connect()

        try:
            if self.db_type == 'sqlite':
                connection.execute(text("PRAGMA journal_mode = WAL"))
                connection.execute(text("PRAGMA synchronous = NORMAL"))
                connection.execute(text("PRAGMA cache_size = 1000"))
                logger.info("SQLite性能优化配置已应用")

            elif self.db_type == 'mysql':
                connection.execute(text("SET sql_mode = 'STRICT_TRANS_TABLES'"))
                logger.info("MySQL严格模式已启用")

        except Exception as e:
            logger.warning(f"数据库特定配置应用失败: {str(e)}")
        finally:
            connection.close()

    def get_compatibility_status(self):
        
        info = get_database_info(self.db_engine)
        info['health'] = validate_connection_health(self.db_engine)
        info['type'] = self.db_type
        return info