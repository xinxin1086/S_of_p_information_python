class Config:
    # 数据库配置（所有模块共享）
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:root@localhost:3306/s_of_p_information?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT配置
    JWT_SECRET_KEY = 'your-secret-key-123'  # 生产环境需更换
    JWT_EXPIRATION_DELTA = 3600  # 令牌有效期（秒）