# 日志订阅

# Components

## POST 查询订阅数据

> Body 请求参数

```json
{
  "token": "xxxx-xxxx-xxxx-xxxx",
  "source_id": "audit_log",
  "start_time": 1700000000000,
  "end_time": 1700600000000,
  "page": 1,
  "page_size": 10,
  "fields": ["field1", "field2"],
  "filters": {
    "condition": {
      "field": {
        "table": "table_name",
        "raw_name": "user_name",
        "display_name": "user_name",
        "field_type": "string"
      },
      "operator": "eq",
      "filters": ["admin"]
    }
  }
}
```

### 请求参数

| 名称 | 位置 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- | --- |
| body | body | [LogSubscriptionQuerySerializer](#schemalogsubscriptionqueryserializer) | 是 | 请求体 |

> 返回示例

```json
{
  "result": true,
  "code": 0,
  "message": "OK",
  "data": {
    "page": 1,
    "page_size": 10,
    "total": 100,
    "results": [
      {
        "dtEventTimeStamp": 1700000000000,
        "system_id": "bk_log",
        "action_id": "create",
        "user_name": "admin",
        "resource_id": "res_001"
      }
    ],
    "query_sql": "SELECT * FROM ...",
    "count_sql": "SELECT COUNT(*) ..."
  }
}
```

### 返回结果

| 状态码 | 状态码含义 | 说明 | 数据模型 |
| --- | --- | --- | --- |
| 200 | OK | 成功 | [LogSubscriptionQueryResponse](#schemalogsubscriptionqueryresponse) |

### 返回字段说明

返回的字段取决于数据源的实际字段和订阅配置：

- 如果请求中指定了 `fields` 参数，则只返回指定的字段
- 如果未指定 `fields` 参数，则返回数据源的所有字段（SELECT *）
- 字段名称和类型由 BKBase/Doris 中的实际表结构决定

常见字段示例：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| dtEventTimeStamp | integer | 事件时间戳（毫秒） |
| system_id | string | 系统 ID |
| action_id | string | 操作 ID |
| user_name | string | 用户名 |
| resource_id | string | 资源 ID |
| event_content | string | 事件内容 |

> 提示：`data.results` 中的字段完全由数据源决定，调用方需要根据实际数据源的字段结构进行解析。

# 数据模型

<h2 id="tocS_LogSubscriptionQuerySerializer">LogSubscriptionQuerySerializer</h2>

```json
{
  "token": "string",
  "source_id": "string",
  "start_time": 0,
  "end_time": 0,
  "page": 1,
  "page_size": 10,
  "fields": ["string"],
  "filters": {
    "condition": {
      "field": {
        "table": "string",
        "raw_name": "string",
        "display_name": "string",
        "field_type": "string"
      },
      "operator": "string",
      "filters": ["string"]
    }
  }
}
```

| 名称 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- |
| token | string | 是 | 订阅 token（UUID 格式） |
| source_id | string | 是 | 数据源唯一标识 |
| start_time | integer | 是 | 起始时间（Unix 毫秒时间戳） |
| end_time | integer | 是 | 结束时间（Unix 毫秒时间戳） |
| page | integer | 是 | 页码（从 1 开始） |
| page_size | integer | 是 | 每页数量（最大 1000） |
| fields | array[string] | 否 | 指定返回字段列表，为空则返回所有字段 |
| filters | object | 否 | 自定义筛选条件（WhereCondition 格式） |
| raw | boolean | 否 | 是否只返回 SQL 而不执行查询（默认 false） |

### filters 字段说明

`filters` 参数用于在订阅配置的基础上添加额外的筛选条件，格式为 `WhereCondition` 对象：

```json
{
  "condition": {
    "field": {
      "table": "table_name",
      "raw_name": "field_name",
      "display_name": "field_name",
      "field_type": "string"
    },
    "operator": "eq",
    "filters": ["value"]
  }
}
```

或使用 `conditions` 数组支持多条件组合：

```json
{
  "connector": "and",
  "conditions": [
    {
      "condition": {
        "field": {...},
        "operator": "eq",
        "filters": ["value1"]
      }
    },
    {
      "condition": {
        "field": {...},
        "operator": "like",
        "filters": ["%value2%"]
      }
    }
  ]
}
```

支持的操作符：
- `eq`: 等于
- `neq`: 不等于
- `gt`: 大于
- `lt`: 小于
- `gte`: 大于等于
- `lte`: 小于等于
- `include`: IN（包含）
- `exclude`: NOT IN（不包含）
- `like`: LIKE（模糊匹配）
- `not_like`: NOT LIKE
- `between`: BETWEEN（范围）

<h2 id="tocS_LogSubscriptionQueryResponse">LogSubscriptionQueryResponse</h2>

```json
{
  "result": true,
  "code": 0,
  "message": "OK",
  "data": {
    "page": 1,
    "page_size": 10,
    "total": 100,
    "results": [
      {
        "field1": "value1",
        "field2": "value2"
      }
    ],
    "query_sql": "string",
    "count_sql": "string"
  }
}
```

| 名称 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- |
| result | boolean | 是 | 是否成功（true 表示成功，false 表示失败） |
| code | integer | 是 | 错误码（0 表示成功） |
| message | string | 是 | 错误信息 |
| data | object | 是 | 业务数据 |
| data.page | integer | 是 | 当前页码 |
| data.page_size | integer | 是 | 每页数量 |
| data.total | integer | 是 | 总记录数 |
| data.results | array | 是 | 订阅结果列表（字段由数据源决定） |
| data.query_sql | string | 是 | 查询 SQL（用于调试） |
| data.count_sql | string | 是 | 统计 SQL（用于调试） |

## 错误码说明

| 错误码 | 说明 |
| --- | --- |
| 0 | 成功 |
| 1302100 | 订阅配置不存在或未启用 |
| 1302101 | 数据源不存在或未启用 |
| 1302102 | 数据源不在订阅配置中 |

## 使用示例

### 1. 基础查询（返回所有字段）

```bash
curl -X POST "https://your-domain/api/v1/log_subscription/apigw/query/" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "550e8400-e29b-41d4-a716-446655440000",
    "source_id": "audit_log",
    "start_time": 1700000000000,
    "end_time": 1700600000000,
    "page": 1,
    "page_size": 10
  }'
```

### 2. 指定返回字段

```bash
curl -X POST "https://your-domain/api/v1/log_subscription/apigw/query/" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "550e8400-e29b-41d4-a716-446655440000",
    "source_id": "audit_log",
    "start_time": 1700000000000,
    "end_time": 1700600000000,
    "page": 1,
    "page_size": 10,
    "fields": ["dtEventTimeStamp", "system_id", "action_id", "user_name"]
  }'
```

### 3. 添加自定义筛选条件

```bash
curl -X POST "https://your-domain/api/v1/log_subscription/apigw/query/" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "550e8400-e29b-41d4-a716-446655440000",
    "source_id": "audit_log",
    "start_time": 1700000000000,
    "end_time": 1700600000000,
    "page": 1,
    "page_size": 10,
    "filters": {
      "condition": {
        "field": {
          "table": "591_audit_log.doris",
          "raw_name": "user_name",
          "display_name": "user_name",
          "field_type": "string"
        },
        "operator": "like",
        "filters": ["%admin%"]
      }
    }
  }'
```

### 4. 只获取 SQL（不执行查询）

```bash
curl -X POST "https://your-domain/api/v1/log_subscription/apigw/query/" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "550e8400-e29b-41d4-a716-446655440000",
    "source_id": "audit_log",
    "start_time": 1700000000000,
    "end_time": 1700600000000,
    "page": 1,
    "page_size": 10,
    "raw": true
  }'
```
