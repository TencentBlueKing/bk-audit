# 日志数据订阅功能开发方案

## 一、需求概述

审计中心需要提供日志数据订阅接口注册至 APIGW 供三方使用，并提供订阅配置后台管理能力。

### 核心需求

1. **订阅配置数据源**：每个数据源包含唯一标识及必须筛选字段等配置信息
2. **订阅配置**：支持配置名、描述、是否启用以及 N 个订阅配置项（Admin 页面支持复制）
3. **订阅配置项**：支持指定多个数据源+筛选条件
    - **必须筛选字段校验**：如果数据源定义了必须筛选字段（如 `system_id`），则配置项的筛选条件中必须包含对这些字段的筛选
    - **多数据源合并校验**：配置项可以关联多个数据源，筛选条件需要满足所有数据源的必须筛选字段要求
    - **多配置项 OR 逻辑**：同一订阅配置的多个配置项如果包含相同数据源，查询时使用 OR 连接
4. **订阅调试**：支持在管理后台进行简易调试能力
5. **订阅查询**：支持 Token 鉴权、时间范围、数据源指定、字段筛选、自定义返回字段

### 与事件订阅的区别

| 对比项    | 风险事件订阅                 | 日志数据订阅                                |
|--------|------------------------|---------------------------------------|
| 数据源    | 固定（事件、风险、策略、标签多表 JOIN） | 可配置多个独立数据源                            |
| 配置结构   | 单一订阅配置 + 筛选条件          | 订阅配置 + 多个配置项                          |
| 数据源选择  | 不支持                    | 查询时必须指定 source_id                     |
| 返回字段   | 固定全量字段                 | 支持自定义返回字段                             |
| 必须筛选字段 | 无                      | 支持数据源级别的必须筛选字段校验（配置项选择数据源后必须配置相应字段筛选） |
| 字段管理   | 预定义字段列表                | 不管理字段，交由 SQL 查询时数据库校验                 |

---

## 二、模块结构

### 2.1 目录位置

**位置**：`services/web/log_subscription/`

```
services/web/
├── log_subscription/          # 日志订阅模块
│   ├── __init__.py
│   ├── models.py             # 数据模型
│   ├── serializers.py        # 序列化器
│   ├── resources/            # API 资源
│   │   ├── __init__.py
│   │   └── subscription.py  # 查询资源
│   ├── exceptions.py         # 异常定义
│   ├── admin.py             # Admin 管理
│   ├── views.py             # ViewSet
│   ├── urls.py              # URL 路由
│   ├── apps.py              # App 配置
│   └── migrations/
│       └── 0001_initial.py   # 数据库迁移
```

### 2.2 App 注册

在 `services/web/settings.py` 的 `INSTALLED_APPS` 中添加：

```python
INSTALLED_APPS = [
    # ... 其他 app
    "services.web.log_subscription",
]
```

### 2.3 配置项

在 `config/default.py` 中配置：

```python
# 日志订阅查询最大时间范围（毫秒），默认 30 天
LOG_SUBSCRIPTION_MAX_TIME_RANGE = int(
    os.getenv("BKAPP_LOG_SUBSCRIPTION_MAX_TIME_RANGE", str(30 * 24 * 60 * 60 * 1000))
)
```

---

## 三、数据模型设计

### 3.1 日志数据源配置模型 (`LogDataSource`)

**文件位置**: `services/web/query/log_subscription/models.py`

**继承**: `OperateRecordModel`（不使用软删除）

**核心字段**:

| 字段名                      | 类型           | 说明          | 备注                                |
|--------------------------|--------------|-------------|-----------------------------------|
| `source_id`              | CharField    | 数据源唯一标识     | unique=True, 如 "audit_log"        |
| `name`                   | CharField    | 数据源名称       | 如 "审计日志"                          |
| `namespace`              | CharField    | 命名空间        | 默认 `settings.DEFAULT_NAMESPACE`   |
| `bkbase_table_id`        | CharField    | BKBase 表 ID | 如 "591_bkaudit_event"             |
| `storage_type`           | CharField    | 存储类型        | 使用 `StorageType` 枚举，默认 `doris`    |
| `required_filter_fields` | JSONField    | 必须筛选字段列表    | 如 `["system_id", "namespace"]`    |
| `time_field`             | CharField    | 时间字段名       | 默认 `TIMESTAMP_PARTITION_FIELD` 常量 |
| `is_enabled`             | BooleanField | 是否启用        | 默认 True                           |

**核心方法**:

- `get_table_name()`: 返回 `{bkbase_table_id}.{storage_type}`
- `validate_required_fields(condition)`: 验证筛选条件是否包含所有必须筛选字段

**设计要点**:

- 不使用软删除，避免 `source_id` 唯一约束冲突
- 使用 `is_enabled` 控制启用状态
- 不管理字段元数据，字段校验交由 SQL 查询时数据库处理
- 必须筛选字段只校验字段名是否在条件中，不校验字段是否真实存在

### 3.2 日志订阅配置模型 (`LogSubscription`)

**继承**: `SoftDeleteModel`（使用软删除）

**核心字段**:

| 字段名           | 类型           | 说明       | 备注                                     |
|---------------|--------------|----------|----------------------------------------|
| `name`        | CharField    | 配置名称     | -                                      |
| `description` | TextField    | 配置描述     | -                                      |
| `token`       | UUIDField    | 订阅 Token | 使用 `core.models.UUIDField`，unique=True |
| `is_enabled`  | BooleanField | 是否启用     | 默认 True                                |

**核心方法**:

- `get_data_sources()`: 获取该订阅配置关联的所有数据源

**设计要点**:

- 使用软删除，保留历史订阅记录
- Token 用于 API 查询鉴权

### 3.3 日志订阅配置项模型 (`LogSubscriptionItem`)

**继承**: `OperateRecordModel`（不使用软删除）

**核心字段**:

| 字段名            | 类型              | 说明     | 备注                |
|----------------|-----------------|--------|-------------------|
| `subscription` | ForeignKey      | 所属订阅配置 | CASCADE 删除        |
| `name`         | CharField       | 配置项名称  | 不要求唯一             |
| `description`  | TextField       | 配置项描述  | -                 |
| `data_sources` | ManyToManyField | 关联的数据源 | 支持多个数据源           |
| `condition`    | JSONField       | 筛选条件   | WhereCondition 格式 |
| `order`        | IntegerField    | 排序     | 默认 0              |

**核心方法**:

- `get_where_condition()`: 解析并返回 WhereCondition 对象
- `validate_condition_with_sources()`: 验证筛选条件是否满足所有数据源的必须筛选字段要求

**设计要点**:

- 不使用软删除，通过 CASCADE 关联主记录
- `condition` 中的 `field.table` 在配置时给默认值（如 "t"），查询时会被自动重写
- 支持多个数据源，筛选条件需满足所有数据源的必须筛选字段要求

---

## 四、核心实现逻辑

### 4.1 SQL 构建

**实现位置**: `services/web/log_subscription/resources/subscription.py`

**设计思路**:

- 直接使用 `core.sql.builder` 的基础组件（`BKBaseQueryBuilder`, `BkBaseComputeSqlGenerator`）
- 使用 `WhereCondition` Pydantic 模型处理条件
- 使用 `SQLGenerator` 的 `generate()` 和 `generate_count()` 方法

**核心功能**:

1. **条件组装** (`_build_where_condition`)
    - 时间范围条件（必须）
    - 订阅配置的筛选条件（可能是多个配置项的 OR 组合）
    - 用户自定义筛选条件
    - 所有条件使用 AND 连接
    - **统一表名替换**：在最后统一调用 `_replace_table_name()` 替换所有 `field.table` 占位符

2. **表名替换** (`_replace_table_name`)
    - 递归替换 `WhereCondition` 中所有 `Field` 的 `table` 属性
    - **原地修改**：直接修改原对象，不创建新对象
    - 只处理 `field.table`，保留其他所有属性（`filter`, `filters`, `connector` 等）

3. **字段处理** (`_build_select_fields`)
    - 未指定字段：返回空列表，SQL 生成器会生成 `SELECT *`
    - 指定字段：返回指定字段列表
    - 字段类型统一为 `STRING`，实际类型由数据库决定

4. **SQL 生成**
    - 使用 `BkBaseComputeSqlGenerator.generate()` 生成查询 SQL
    - 使用 `BkBaseComputeSqlGenerator.generate_count()` 生成统计 SQL

### 4.2 API 资源 (`QueryLogSubscription`)

**文件位置**: `services/web/log_subscription/resources/subscription.py`

**查询流程**:

1. **验证 Token** (`_get_subscription`)
    - 将 UUID 对象转换为 hex 格式（数据库中存储的是无连字符的 hex 格式）
    - 根据 token 获取启用的订阅配置（使用 `objects.filter`，自动过滤软删除）
    - 预加载 items 和 data_sources

2. **验证数据源** (`_get_data_source`)
    - 根据 source_id 获取启用的数据源
    - 验证数据源是否在订阅配置中

3. **获取订阅条件** (`_get_subscription_condition`)
    - 查找所有包含目标数据源的配置项
    - 多个配置项的条件使用 `FilterConnector.OR` 连接
    - 单个配置项直接返回

4. **解析自定义条件** (`_parse_custom_condition`)
    - 验证并解析用户传入的 WhereCondition

5. **构建并执行 SQL**
    - 组装完整的 WHERE 条件（时间 + 订阅条件 + 自定义条件）
    - 统一替换所有条件中的表名占位符
    - 使用 `BkBaseComputeSqlGenerator` 生成 SQL
    - 调用 `api.bk_base.query_sync.bulk_request` 并发执行查询和统计
    - 返回分页结果

**多配置项 OR 逻辑示例**:

```
订阅配置包含：
- 配置项1: 数据源 [A, B], 条件: system_id = 'bk_cmdb'
- 配置项2: 数据源 [B, C], 条件: system_id = 'bk_job'

查询 source_id = B:
最终 WHERE = (条件1 OR 条件2) AND 时间范围 AND 用户条件
```

### 4.3 序列化器设计

**文件位置**: `services/web/log_subscription/serializers.py`

**请求序列化器** (`LogSubscriptionQuerySerializer`):

- `token`: UUID 格式的订阅 Token
- `source_id`: 数据源标识
- `start_time`, `end_time`: Unix 毫秒时间戳
- `page`, `page_size`: 分页参数
- `fields`: 可选的返回字段列表
- `filters`: 可选的自定义筛选条件（WhereCondition 格式）
- `raw`: 是否仅返回 SQL 不执行查询

**校验逻辑**:

1. **时间范围校验** (`validate`):
   - 开始时间需小于等于结束时间
   - 时间范围不能超过配置的最大值（`LOG_SUBSCRIPTION_MAX_TIME_RANGE`，默认 30 天）

2. **Keys 字段校验** (`validate_filters`):
   - 递归检查 `field.keys` 字段（暂不支持）
   - 参考 `_replace_table_name` 的实现方式，只检查 `field` 对象中的 `keys` 属性
   - 如果包含 `keys` 字段，抛出 `ValidationError`

**响应序列化器** (`LogSubscriptionQueryResponseSerializer`):

- `page`, `page_size`, `total`: 分页信息
- `results`: 查询结果列表
- `query_sql`, `count_sql`: 实际执行的 SQL

### 4.4 异常定义

**文件位置**: `services/web/query/log_subscription/exceptions.py`

- `LogSubscriptionNotFound`: 订阅配置不存在或未启用（404）
- `DataSourceNotFound`: 数据源不存在或未启用（404）
- `DataSourceNotInSubscription`: 数据源不在订阅配置中（403）

---

## 五、Admin 后台管理

**文件位置**: `services/web/query/log_subscription/admin.py`

### 5.1 数据源管理 (`LogDataSourceAdmin`)

**功能**:

- 列表展示：source_id, name, namespace, storage_type, is_enabled
- 搜索：source_id, name, description
- 过滤：namespace, storage_type, is_enabled
- 字段分组：基本信息、表配置、必须筛选字段、审计信息

### 5.2 订阅配置管理 (`LogSubscriptionAdmin`)

**功能**:

- 列表展示：name, token, is_enabled, 配置项数量
- 搜索：name, token, description
- 过滤：is_enabled, is_deleted
- 内联编辑：LogSubscriptionItemInline
- 支持"另存为"功能：复制订阅配置时自动生成新 Token

### 5.3 配置项管理 (`LogSubscriptionItemAdmin`)

**功能**:

- 列表展示：subscription, name, 数据源列表, order
- 搜索：name, description
- 过滤：subscription
- 表单：
    - 使用 `WhereConditionWidget` 编辑筛选条件
    - 不提供预定义字段选项，用户手动输入字段名
    - 支持 filter_horizontal 选择多个数据源
    - **数据源过滤**：只显示启用的数据源（`is_enabled=True`）
- 保存验证：
    - 保存后调用 `validate_condition_with_sources()` 验证必须筛选字段
    - 验证失败时显示错误消息并阻止保存

**关键说明**:

- `field.table` 在配置时给默认值即可（如 "t"），查询时会被自动替换
- 数据源停用后，订阅配置中无法再选择该数据源

### 5.4 订阅调试界面

**访问方式**:

在订阅详情页面点击右上角"验证 SQL"按钮，或直接访问：
```
/admin/log_subscription/logsubscription/<订阅ID>/preview-sql/
```

**功能特性**:

- ✅ 数据源选择下拉框（自动填充订阅配置关联的数据源）
- ✅ 时间范围选择器（datetime-local 格式）
- ✅ 分页参数配置
- ✅ 返回字段自定义（逗号分隔）
- ✅ **自定义筛选条件**：使用与配置界面相同的 WhereConditionWidget
- ✅ 仅生成 SQL 模式（验证 SQL 语法）
- ✅ 生成并执行查询模式（查看真实数据）
- ✅ SQL 展示区域（Query SQL + Count SQL）
- ✅ 查询结果表格展示
- ✅ 错误提示和成功消息

**使用场景**:

1. **验证订阅配置**：新建配置后验证 SQL 是否正确
2. **测试查询结果**：查看实际的查询数据
3. **调试筛选条件**：确认筛选条件是否符合预期
4. **测试自定义字段**：验证指定字段是否正确返回

---

## 六、URL 路由配置

**文件位置**: `services/web/log_subscription/urls.py`

使用 `ResourceRouter` 自动注册资源：

```python
from bk_resource.viewsets import ResourceRouter
from services.web.log_subscription import views

router = ResourceRouter()
router.register_module(views)

urlpatterns = router.urls
```

**主 URL 配置**:

```python
# services/web/urls.py
path("api/v1/log_subscription/", include("services.web.log_subscription.urls")),
```

**API 端点**:

- `POST /api/v1/log_subscription/apigw/query/`: APIGW 接口（日志订阅查询）
- `POST /api/v1/log_subscription/log_subscription/query/`: 用户接口（包括 Admin 调试）

---

## 七、数据库迁移

### 创建迁移

```bash
python manage.py makemigrations log_subscription --name=initial
```

### 执行迁移

```bash
python manage.py migrate log_subscription
```

---

## 八、使用示例

### 8.1 配置数据源

```python
from services.web.query.log_subscription.models import LogDataSource

# 创建审计日志数据源
audit_source = LogDataSource.objects.create(
    source_id="audit_log",
    name="审计日志",
    namespace="default",
    bkbase_table_id="591_bkaudit_event",
    storage_type="doris",
    required_filter_fields=["system_id"],  # 必须筛选 system_id
    time_field="dtEventTimeStamp",
    is_enabled=True
)
```

### 8.2 配置订阅（多配置项示例）

```python
from services.web.query.log_subscription.models import (
    LogSubscription,
    LogSubscriptionItem
)

# 创建订阅
subscription = LogSubscription.objects.create(
    name="多系统日志订阅",
    description="订阅 bk_cmdb 和 bk_job 的审计日志",
    is_enabled=True
)

# 配置项1: 订阅 bk_cmdb 的审计日志
item1 = LogSubscriptionItem.objects.create(
    subscription=subscription,
    name="CMDB 审计日志",
    condition={
        "condition": {
            "field": {
                "table": "t",  # 默认值，查询时会被替换
                "raw_name": "system_id",
                "display_name": "system_id",
                "field_type": "string"
            },
            "operator": "=",
            "filters": ["bk_cmdb"]
        }
    }
)
item1.data_sources.add(audit_source)

# 配置项2: 订阅 bk_job 的审计日志
item2 = LogSubscriptionItem.objects.create(
    subscription=subscription,
    name="JOB 审计日志",
    condition={
        "condition": {
            "field": {
                "table": "t",
                "raw_name": "system_id",
                "display_name": "system_id",
                "field_type": "string"
            },
            "operator": "=",
            "filters": ["bk_job"]
        }
    }
)
item2.data_sources.add(audit_source)

# 查询时的 SQL WHERE 条件会是:
# (system_id = 'bk_cmdb' OR system_id = 'bk_job') 
# AND dtEventTimeStamp BETWEEN ... 
# AND 用户自定义条件
```

### 8.3 查询数据

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
    "fields": ["system_id", "username", "action"],
    "filters": {
      "condition": {
        "field": {
          "table": "t",
          "raw_name": "username",
          "display_name": "username",
          "field_type": "string"
        },
        "operator": "=",
        "filters": ["admin"]
      }
    }
  }'
```

---

## 九、核心设计要点

### 9.1 软删除策略

| 模型                    | 是否软删除 | 理由                                        |
|-----------------------|-------|-------------------------------------------|
| `LogDataSource`       | ❌ 否   | `source_id` 唯一约束与软删除冲突；使用 `is_enabled` 控制 |
| `LogSubscription`     | ✅ 是   | 需要保留历史订阅记录                                |
| `LogSubscriptionItem` | ❌ 否   | 通过 `CASCADE` 关联，主记录删除时自动删除                |

### 9.2 字段管理策略

**不管理字段元数据**:

- ✅ 配置简单，表结构变更无需同步
- ✅ 更加灵活，支持任意字段查询
- ❌ 字段错误只能在查询时发现
- ❌ Admin 界面无法提供字段下拉选择

**必须筛选字段校验**:

- ✅ 配置时只校验字段名是否在条件中
- ❌ 不校验字段是否真实存在于表中
- ✅ 字段是否存在交由 SQL 查询时数据库校验

### 9.3 多配置项 OR 逻辑

**场景**:

```
订阅配置包含：
- 配置项1: 数据源 [A, B], 条件1
- 配置项2: 数据源 [B, C], 条件2

查询 source_id = B:
最终 WHERE = (条件1 OR 条件2) AND 时间范围 AND 用户条件
```

**实现**:

- `_get_subscription_condition()` 查找所有包含目标数据源的配置项
- 将这些配置项的条件用 `Connector.OR` 连接
- 在 `_merge_conditions()` 中与时间条件、用户条件用 `AND` 连接

### 9.4 field.table 处理

**配置时**:

- 用户配置筛选条件时，`field.table` 给默认值（如 `"t"`）
- 不需要关心实际查询哪个数据源

**查询时**:

- `_normalize_condition()` 深拷贝条件
- `_rewrite_table_alias()` 递归重写所有 `field.table` 为实际表别名
- 确保 SQL 生成时使用正确的表引用

### 9.5 常量使用

- `time_field` 默认值使用 `TIMESTAMP_PARTITION_FIELD` 常量（来自 `services.web.query.constants`）
- `storage_type` 使用 `StorageType` 枚举（来自 `api.bk_base.constants`）
- `connector` 使用 `FilterConnector` 枚举（来自 `core.sql.constants`）
- 避免硬编码字符串

---

## 十、注意事项

### 10.1 性能优化

1. **分页限制**: 单次查询最多返回 1000 条数据
2. **时间范围限制**: 限制单次查询时间范围（通过 `LOG_SUBSCRIPTION_MAX_TIME_RANGE` 配置，默认 30 天）
3. **索引优化**: 确保 Doris 表的时间字段有索引
4. **字段选择**: 建议指定需要的字段而不是 SELECT *
5. **预加载**: 查询订阅配置时预加载 items 和 data_sources

### 10.4 配置说明

**环境变量**:

- `BKAPP_LOG_SUBSCRIPTION_MAX_TIME_RANGE`: 日志订阅查询最大时间范围（毫秒），默认 30 天

**配置位置**: `config/default.py`

```python
LOG_SUBSCRIPTION_MAX_TIME_RANGE = int(
    os.getenv("BKAPP_LOG_SUBSCRIPTION_MAX_TIME_RANGE", str(30 * 24 * 60 * 60 * 1000))
)
```

### 10.2 安全考虑

1. **Token 管理**: Token 一旦泄露需要及时更换（通过"另存为"功能）
2. **权限控制**: 通过订阅配置的筛选条件限制数据范围
3. **查询限流**: 建议在网关层实施限流策略
4. **SQL 注入防护**: 使用参数化查询，避免直接拼接字段名

### 10.3 监控告警

1. **查询性能**: 监控 SQL 执行时间
2. **查询频率**: 监控每个 Token 的查询频率
3. **错误率**: 监控查询失败率（字段不存在等）
4. **数据量**: 监控单次查询返回数据量

---

## 十一、FAQ

### Q1: 为什么放在 `services/web/query` 下？

A: 日志数据订阅本质上是查询功能的扩展，与现有的 `CollectorSearch` 等查询资源属于同一领域。

### Q2: 为什么不管理字段元数据？

A:

- **优点**: 配置简单，表结构变更无需同步，更灵活
- **缺点**: 字段错误只能在查询时发现，Admin 无法提供字段下拉
- **权衡**: 对于日志订阅场景，灵活性比提前校验更重要

### Q3: 多配置项的 OR 逻辑是如何工作的？

A: 当多个配置项包含相同数据源时，查询时会将这些配置项的条件用 OR 连接，然后与时间条件、用户条件用 AND 连接。这样可以实现"
订阅多个系统的日志"的场景。

### Q4: field.table 在配置时需要关注吗？

A: 不需要。配置时给一个默认值（如 "t"）即可，查询时会被自动替换为实际的表别名。这样配置与查询解耦，配置更简单。

### Q5: 如何保证必须筛选字段被正确配置？

A: 在保存配置项时，`validate_condition_with_sources()` 会检查筛选条件是否包含所有关联数据源的必须筛选字段。注意：只校验字段名是否在条件中，不校验字段是否真实存在于表中。

### Q6: 为什么 LogSubscriptionItem 不使用软删除？

A: 配置项作为订阅配置的子项，通过 CASCADE 关联即可。主记录软删除时，配置项也会被软删除。单独对配置项软删除会增加查询复杂度，且没有实际业务价值。

### Q7: 如何调试订阅配置？

A:

1. 在 API 请求中设置 `raw=true`，只返回 SQL 不执行查询
2. 在 Admin 后台可以添加调试视图（可选功能）
3. 查看返回的 `query_sql` 和 `count_sql` 字段

---

## 十二、后续优化方向

1. **字段元数据管理**（可选）: 如果需要更好的用户体验，可以考虑从 BKBase 动态获取表字段信息
2. **字段映射**: 支持字段别名映射，屏蔽底层表结构
3. **数据导出**: 支持大批量数据导出（异步任务）
4. **订阅统计**: 提供订阅使用统计报表
5. **实时订阅**: 支持 Webhook 推送实时数据
6. **查询模板**: 提供常用查询条件模板
7. **字段黑名单**: 配置禁止查询的敏感字段列表
8. **订阅调试界面**: 在 Admin 后台提供更完善的调试功能

---

## 十三、实现状态

### 已完成功能

- ✅ 数据模型（LogDataSource, LogSubscription, LogSubscriptionItem）
- ✅ Admin 管理界面（数据源管理、订阅配置管理、配置项内联编辑）
- ✅ Admin 调试界面（SQL 预览、查询执行、自定义筛选条件）
- ✅ API 接口（查询接口、APIGW 注册）
- ✅ 序列化器（请求/响应序列化、keys 字段校验、时间范围校验）
- ✅ SQL 构建（条件组装、表名替换、字段处理）
- ✅ 必须筛选字段校验
- ✅ 多配置项 OR 逻辑
- ✅ 单元测试（18 个测试用例，100% 通过）

### 关键实现细节

1. **表名替换**：使用原地修改方式，递归替换所有 `field.table` 占位符
2. **Keys 字段校验**：在序列化器中递归检查 `field.keys`，暂不支持
3. **数据源过滤**：Admin 中只显示启用的数据源
4. **时间范围配置**：通过环境变量 `BKAPP_LOG_SUBSCRIPTION_MAX_TIME_RANGE` 配置

---

**文档版本**: v2.0  
**最后更新**: 2025-12-22  
**作者**: Claude + Raja
