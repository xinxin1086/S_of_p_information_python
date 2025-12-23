# API_admin 测试文档

## 测试概述

本文档包含 API_admin 模块的完整测试用例，覆盖了所有主要功能和边界情况。

## 测试结构

```
tests/API_admin/
├── conftest.py              # 测试配置和工具函数
├── test_content.py          # 内容管理接口测试
├── test_statistics.py       # 统计分析接口测试
├── test_common.py           # 公共工具测试
└── README.md               # 本文档
```

## 测试用例分类

### 1. 内容管理接口测试 (test_content.py)

- **待审核内容查询** (`TestPendingContent`)
  - 获取所有待审核内容
  - 按模块筛选
  - 分页查询
  - 权限验证测试

- **批量审核** (`TestBatchReview`)
  - 批量通过
  - 批量拒绝
  - 批量要求修改
  - 空列表处理
  - 无效模块处理
  - 权限验证测试

- **内容详情查看** (`TestContentDetail`)
  - 科普文章详情
  - 活动详情
  - 内容不存在处理
  - 无效模块处理
  - 权限验证测试

- **内容导出** (`TestContentExport`)
  - CSV格式导出
  - JSON格式导出
  - 日期范围筛选
  - 无效格式处理
  - 权限验证测试

- **用户显示信息更新** (`TestUpdateUserDisplays`)
  - 成功更新
  - 权限验证测试

- **内容统计** (`TestContentStatistics`)
  - 获取内容统计
  - 权限验证测试

### 2. 统计分析接口测试 (test_statistics.py)

- **用户增长统计** (`TestUserGrowthStats`)
  - 成功获取统计数据
  - 自定义日期范围
  - 按周/月统计
  - 无效日期范围处理
  - 无效统计周期处理
  - 权限验证测试

- **内容发布统计** (`TestContentPublishingStats`)
  - 成功获取统计数据
  - 按内容类型筛选
  - 日期范围筛选
  - 权限验证测试

- **活动参与度统计** (`TestActivityEngagementStats`)
  - 成功获取统计数据
  - 按活动类型筛选
  - 日期范围筛选
  - 图表数据结构验证
  - 权限验证测试

- **系统使用情况统计** (`TestSystemUsageStats`)
  - 成功获取统计数据
  - 数据库统计结构验证
  - 增长趋势图表验证
  - 按周期统计
  - 权限验证测试

- **统计数据导出** (`TestStatisticsExport`)
  - 用户增长数据导出（CSV/JSON）
  - 内容发布数据导出
  - 活动参与度数据导出
  - 系统使用概况导出
  - 无效格式处理
  - 权限验证测试

### 3. 公共工具测试 (test_common.py)

- **日期范围验证** (`TestValidateDateRange`)
  - 有效日期范围
  - 开始日期晚于结束日期
  - 未来日期处理
  - 超长日期范围
  - 无效日期格式
  - 空/部分日期范围

- **敏感数据加密** (`TestEncryptSensitiveData`)
  - 字符串加密
  - 空字符串加密
  - Unicode字符串加密

- **CSV导出功能** (`TestExportToCSV`)
  - 字典数据导出
  - 列表数据导出
  - 无头部导出
  - 空数据导出

- **超级管理员权限装饰器** (`TestSuperAdminRequired`)
  - 超级管理员权限验证成功
  - 普通管理员权限被拒绝
  - 无角色属性用户被拒绝

- **管理员操作日志记录** (`TestLogAdminOperation`)
  - 基本操作日志记录
  - 最小数据日志记录

- **批量更新用户显示信息** (`TestBatchUpdateUserDisplay`)
  - 返回结构验证

- **系统安全检查** (`TestCheckSystemSecurity`)
  - 返回结构验证
  - 默认密码检测

- **集成测试** (`TestIntegration`)
  - 装饰器与日志记录集成测试

## 运行测试

### 运行所有API_admin测试
```bash
pytest tests/API_admin/ -v
```

### 运行特定模块测试
```bash
# 内容管理接口测试
pytest tests/API_admin/test_content.py -v

# 统计分析接口测试
pytest tests/API_admin/test_statistics.py -v

# 公共工具测试
pytest tests/API_admin/test_common.py -v
```

### 运行特定测试类
```bash

# 只运行批量审核测试
pytest tests/API_admin/test_content.py::TestBatchReview -v
```

### 运行特定测试方法
```bash
# 只运行一个测试方法
pytest tests/API_admin/test_system.py::TestSystemInfo::test_get_system_info_success -v
```

### 生成覆盖率报告
```bash
pytest tests/API_admin/ --cov=API_admin --cov-report=html
```

## 测试配置

### conftest.py 配置
- 使用SQLite内存数据库进行测试
- 自动创建测试数据
- 提供认证token fixture
- 提供断言工具函数

### 测试数据
- 超级管理员用户
- 普通管理员用户
- 测试用户
- 测试科普文章
- 测试活动

### 断言工具函数
- `assert_success_response()`: 验证成功响应
- `assert_error_response()`: 验证错误响应
- `assert_permission_denied()`: 验证权限被拒绝
- `get_auth_headers()`: 获取认证头信息

## 测试覆盖范围

1. **功能覆盖**: 所有API接口的主要功能
2. **权限覆盖**: 超级管理员和普通管理员的权限差异
3. **参数覆盖**: 正常参数、边界参数、无效参数
4. **异常覆盖**: 网络异常、数据异常、权限异常
5. **集成覆盖**: 多个组件协同工作的场景

## 注意事项

1. **数据库依赖**: 测试使用内存数据库，不会影响生产数据
2. **认证机制**: 测试使用模拟的token，实际的JWT验证在生产环境中进行
3. **外部依赖**: 文件系统操作、外部API调用等使用mock进行模拟
4. **性能测试**: 当前测试主要关注功能正确性，不包含性能测试

## 持续集成

这些测试可以集成到CI/CD流水线中：

```yaml
# .github/workflows/test.yml 示例
name: API Admin Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    - name: Run tests
      run: pytest tests/API_admin/ --cov=API_admin
```

## 扩展测试

当添加新功能时，请按照以下模式添加对应的测试：

1. 为每个新功能创建测试类
2. 包含正常流程、异常流程、权限验证的测试
3. 使用一致的命名规范
4. 添加充分的断言
5. 考虑边界情况和错误场景
6. 更新本文档