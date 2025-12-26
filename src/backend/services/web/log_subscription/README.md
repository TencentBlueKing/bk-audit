# 日志数据订阅功能

## 功能概述

日志数据订阅功能提供了灵活的日志数据查询接口，支持：

- 多数据源配置和管理
- 基于 Token 的订阅鉴权
- 灵活的筛选条件配置
- 自定义返回字段
- 多配置项 OR 逻辑
- Admin 后台管理和配置复制
- 可视化调试界面 ⭐ 新增

## 快速开始

### 1. 创建数据源

```python
from services.web.query.log_subscription.models import LogDataSource

source = LogDataSource.objects.create(
    source_id="audit_log",
    name="审计日志",
    namespace="default",
    bkbase_table_id="591_bkaudit_event",
    storage_type="doris",
    required_filter_fields=["system_id"],  # 必须筛选字段
    time_field="dtEventTimeStamp",
    is_enabled=True
)
```

### 2. 创建订阅配置

```python
from services.web.query.log_subscription.models import LogSubscription, LogSubscriptionItem

# 创建订阅
subscription = LogSubscription.objects.create(
    name="业务系统日志订阅",
    description="提供给业务系统的日志数据",
    is_enabled=True
)

# 创建配置项
item = LogSubscriptionItem.objects.create(
    subscription=subscription,
    name="CMDB 日志",
    condition={
        "condition": {
            "field": {
                "table": "t",
                "raw_name": "system_id",
                "display_name": "system_id",
                "field_type": "string"
            },
            "operator": "eq",  # 注意：使用枚举值 "eq" 而不是 "="
            "filters": ["bk_cmdb"]
        }
    }
)
item.data_sources.add(source)

print(f"订阅 Token: {subscription.token}")
```

### 3. 查询数据

```bash
curl -X POST "http://your-domain/api/v1/log_subscription/query/" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "source_id": "audit_log",
    "start_time": 1704067200000,
    "end_time": 1704153600000,
    "page": 1,
    "page_size": 100,
    "fields": ["system_id", "username", "action"]
  }'
```

## 核心特性

### 多配置项 OR 逻辑

同一订阅配置可以包含多个配置项，查询时会自动使用 OR 连接：

```python
# 配置项1: system_id = 'bk_cmdb'
# 配置项2: system_id = 'bk_job'
# 最终 SQL: WHERE ... AND (system_id='bk_cmdb' OR system_id='bk_job')
```

### 必须筛选字段校验

数据源可以定义必须筛选字段，配置项必须包含这些字段的筛选条件：

```python
# 数据源定义
required_filter_fields = ["system_id", "namespace"]

# 配置项的 condition 必须包含 system_id 和 namespace 的筛选
# 否则保存时会报错
```

### 字段灵活性

不预定义字段列表，支持查询任意字段：

- 未指定 `fields` 参数：返回 `SELECT *`
- 指定 `fields` 参数：返回指定字段
- 字段是否存在由数据库在查询时校验

## API 端点

### POST /api/v1/log_subscription/query/

**请求参数**：

```json
{
  "token": "uuid",
  "source_id": "string",
  "start_time": 1704067200000,
  "end_time": 1704153600000,
  "page": 1,
  "page_size": 100,
  "fields": ["field1", "field2"],  // 可选
  "filters": {  // 可选，自定义筛选条件
    "condition": {
      "field": {...},
      "operator": "eq",
      "filters": [...]
    }
  },
  "raw": false  // 可选，仅返回 SQL 不执行查询
}
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "page": 1,
    "page_size": 100,
    "total": 150,
    "results": [...],
    "query_sql": "SELECT ...",
    "count_sql": "SELECT COUNT(*) ..."
  }
}
```

## 注意事项

### Operator 枚举值

配置筛选条件时，`operator` 必须使用枚举值：

| 符号 | 枚举值 |
|------|--------|
| = | `eq` |
| != | `neq` |
| > | `gt` |
| < | `lt` |
| >= | `gte` |
| <= | `lte` |
| in | `include` |
| not in | `exclude` |
| like | `like` |
| between | `between` |

### field.table 的值

配置时 `field.table` 给默认值（如 `"t"`）即可，查询时会被自动替换为实际表别名。

### 软删除策略

- `LogDataSource`: 不使用软删除，使用 `is_enabled` 控制
- `LogSubscription`: 使用软删除
- `LogSubscriptionItem`: 不使用软删除，CASCADE 关联

## Admin 调试界面 ⭐ 新增

### 访问方式

在订阅详情页面 URL 后添加 `/preview-sql/`：

```
http://your-domain/admin/log_subscription/logsubscription/<订阅ID>/preview-sql/
```

### 功能特性

- ✅ 数据源选择下拉框
- ✅ 时间范围选择器
- ✅ 分页参数配置
- ✅ 返回字段自定义
- ✅ 仅生成 SQL 模式（验证 SQL 语法）
- ✅ 生成并执行查询模式（查看真实数据）
- ✅ SQL 展示区域
- ✅ 查询结果表格展示
- ✅ 错误提示和成功消息

### 使用场景

1. **验证订阅配置**: 新建配置后验证 SQL 是否正确
2. **测试查询结果**: 查看实际的查询数据
3. **调试筛选条件**: 确认筛选条件是否符合预期
4. **测试自定义字段**: 验证指定字段是否正确返回

详细使用指南请参考: [ADMIN_DEBUG_GUIDE.md](./ADMIN_OPERATION_GUIDE.md)

## 开发状态

✅ 数据模型已实现  
✅ SQL 构建器已实现  
✅ API 资源已实现  
✅ Admin 管理已实现  
✅ Admin 调试界面已实现 ⭐  
✅ 数据库迁移已完成  
✅ 单元测试已完成（9 个测试，100% 通过）  
✅ 项目测试已通过（489 个测试，100% 通过）  
✅ 文档已完善  
