# API_user 模块使用说明

## 模块概述

API_user 模块是 Flask 项目的用户管理模块重构版本，提供完整的用户认证、个人信息管理和管理员用户管理功能。

## 文件结构

```
API_user/
├── __init__.py                 # 主模块入口，注册所有Blueprint
├── README.md                  # 本说明文件
├── common/                    # 公共工具模块
│   ├── __init__.py
│   └── utils.py              # 工具函数类
├── user/                      # 用户端接口
│   ├── __init__.py
│   ├── auth.py               # 用户认证相关接口
│   └── profile.py            # 个人信息管理接口
├── admin/                     # 管理员端接口
│   ├── __init__.py
│   └── user_manage.py        # 用户管理接口
├── auth/                      # 认证授权接口
│   ├── __init__.py
│   └── token.py              # JWT token相关接口
└── tests/                     # 测试用例
    ├── __init__.py
    ├── conftest.py           # 测试配置
    ├── test_auth.py          # 认证模块测试
    ├── test_user_profile.py  # 用户个人信息测试
    └── test_admin_management.py # 管理员管理测试
```

## 路由注册指引

### 1. 在主应用中注册模块

在项目的主应用文件（如 `app.py`）中添加以下代码：

```python
# 在 app.py 文件中
from API_user import api_user_bp

# 注册 API_user 模块的 Blueprint
app.register_blueprint(api_user_bp)

print("【应用启动】API_user 模块已注册")
```

### 2. 路由前缀

模块整体使用 `/api/user` 作为前缀，具体路由如下：

#### 认证授权接口 (`/api/user/auth`)
- `POST /api/user/auth/login` - 用户登录
- `POST /api/user/auth/register` - 用户注册
- `POST /api/user/auth/refresh` - 刷新token
- `POST /api/user/auth/verify` - 验证token
- `POST /api/user/auth/logout` - 用户登出
- `POST /api/user/auth/change-password` - 修改密码

#### 用户端接口 (`/api/user/user`)
- `GET /api/user/user/info` - 获取当前用户信息
- `GET /api/user/user/info/<account>` - 获取指定用户信息
- `POST /api/user/user/update` - 更新个人信息
- `POST /api/user/user/avatar` - 上传头像
- `DELETE /api/user/user/avatar` - 删除头像
- `GET /api/user/user/activities` - 获取用户活动记录
- `POST /api/user/user/delete-account` - 注销账号

#### 管理员接口 (`/api/user/admin`)
- `GET /api/user/admin/admins` - 获取管理员列表
- `GET /api/user/admin/users` - 获取用户列表
- `POST /api/user/admin/users` - 创建用户
- `PUT /api/user/admin/users` - 更新用户
- `DELETE /api/user/admin/users` - 删除用户
- `POST /api/user/admin/demote/<admin_id>` - 降级管理员
- `POST /api/user/admin/demote/batch` - 批量降级管理员
- `POST /api/user/admin/create-admin` - 创建管理员
- `GET /api/user/admin/statistics` - 用户统计信息

## 依赖问题说明

### 1. 必需的依赖模块

确保项目中存在以下模块和依赖：

```python
# 必需的导入模块
from components import db, token_required, LocalImageStorage
from components.models import User, Admin
from components.response_service import ResponseService, UserInfoService, handle_api_exception
from components.permission_required import permission_required  # 如果使用权限装饰器
from config import Config
```

### 2. 数据模型依赖

模块依赖以下数据模型，确保它们存在于 `components/models/` 目录：

- `user_models.py` 中的 `User`, `Admin`, `DeletedUser` 模型
- 其他相关模型（如 Activity, ActivityBooking 等）

### 3. 配置依赖

确保 `config.py` 文件中包含以下配置：

```python
# config.py 文件中的必要配置
class Config:
    JWT_SECRET_KEY = 'your-secret-key-here'  # JWT密钥
    SQLALCHEMY_DATABASE_URI = 'your-database-uri'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 其他配置...
```

### 4. 跨模块调用处理

#### 4.1 导入路径更新

原有的导入路径需要更新：

```python
# 旧的导入方式
from user.personal.routes import user_personal_bp
from admin.apis.user_management import user_management_bp

# 新的导入方式
from API_user import api_user_bp
```

#### 4.2 路由调用更新

客户端代码中的API调用路径需要更新：

```javascript
// 旧的API调用
const response = await fetch('/api/user/profile/info');

// 新的API调用
const response = await fetch('/api/user/user/info');
```

### 5. 兼容性处理

为了保持向后兼容，可以在过渡期间同时注册新旧两个模块：

```python
# 在 app.py 中（过渡期间使用）
from API_user import api_user_bp
from user.personal import user_personal_bp  # 旧模块
from admin.apis import user_management_bp  # 旧模块

# 注册新模块
app.register_blueprint(api_user_bp)

# 注释掉旧模块，避免路由冲突
# app.register_blueprint(user_personal_bp)
# app.register_blueprint(user_management_bp)
```

## 测试运行

### 1. 安装测试依赖

```bash
pip install pytest pytest-flask
```

### 2. 运行测试

```bash
# 运行所有测试
cd /app/project_workspace/3963550024011776/API_user/tests
python -m pytest

# 运行特定测试文件
python -m pytest test_auth.py -v

# 运行并显示覆盖率
python -m pytest --cov=. --cov-report=html
```

### 3. 测试数据准备

测试使用内存数据库，每次测试都会创建和销毁，确保测试之间的隔离性。

## 安全注意事项

### 1. JWT密钥管理

确保在生产环境中使用强密钥：

```python
# 生产环境配置
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'your-very-strong-secret-key'
```

### 2. 权限验证

模块使用了装饰器进行权限验证：

- `@token_required` - 基础登录验证
- `@admin_required` - 管理员权限验证
- `@super_admin_required` - 超级管理员权限验证

### 3. 数据验证

所有用户输入都经过严格验证，防止SQL注入和其他安全问题。

## 性能优化建议

### 1. 数据库查询优化

- 使用分页查询避免大量数据加载
- 添加适当的数据库索引
- 使用查询缓存

### 2. 响应格式优化

- 统一使用 `ResponseService` 格式化响应
- 压缩大型响应数据
- 实现响应缓存

## 故障排查

### 1. 常见问题

**问题**: Blueprint 注册失败
**解决**: 检查导入路径和模块依赖

**问题**: JWT token 验证失败
**解决**: 检查 `JWT_SECRET_KEY` 配置和token格式

**问题**: 数据库连接错误
**解决**: 检查数据库配置和连接字符串

### 2. 日志记录

模块中包含详细的日志记录，便于调试：

```python
print(f"【用户登录成功】账号: {account}, 用户类型: {user_type}")
```

## 更新日志

### v1.0.0 (当前版本)
- 完成用户管理模块重构
- 实现JWT认证机制
- 提供完整的测试用例
- 添加详细的权限控制

## 联系方式

如有问题或建议，请联系开发团队。