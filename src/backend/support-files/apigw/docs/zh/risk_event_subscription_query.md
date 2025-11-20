# 风险事件订阅

# Components

## POST 查询订阅数据

> Body 请求参数

```json
{
  "token": "xxxx-xxxx-xxxx-xxxx",
  "start_time": 1700000000000,
  "end_time": 1700600000000,
  "page": 1,
  "page_size": 10
}
```

### 请求参数

| 名称 | 位置 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- | --- |
| body | body | [RiskEventSubscriptionQuerySerializer](#schemariskeventsubscriptionqueryserializer) | 是 | 请求体 |

> 返回示例

```json
{
  "result": true,
  "code": 0,
  "message": "OK",
  "data": {
    "page": 1,
    "page_size": 10,
    "total": 1,
    "results": [
      {
        "event_id": "e20240001",
        "risk_id": "r20240001",
        "strategy_id": 1001,
        "risk_level": "HIGH",
        "dtEventTime": "2024-01-01 12:00:00"
      }
    ],
    "query_sql": "SELECT ...",
    "count_sql": "SELECT COUNT(...) ..."
  }
}
```

### 返回结果

| 状态码 | 状态码含义 | 说明 | 数据模型 |
| --- | --- | --- | --- |
| 200 | OK | 成功 | [RiskEventSubscriptionQueryResponse](#schemariskeventsubscriptionqueryresponse) |

### 返回字段说明

按事件、风险、策略与标签分类说明：

| 字段 | 类别 | 类型 | 说明 |
| --- | --- | --- | --- |
| dtEventTime | 事件 | string | BKBase 字符串时间，格式如 `YYYY-MM-DD HH:mm:ss` |
| dtEventTimeStamp | 事件 | integer | 事件时间戳（毫秒） |
| event_id | 事件 | string | 事件唯一 ID |
| event_content | 事件 | string | 事件内容全文（原始 TEXT） |
| raw_event_id | 事件 | string | 原始事件 ID，用于与风险、策略表关联 |
| strategy_id | 事件 | integer | 告警策略 ID |
| event_evidence | 事件 | string | 事件证据、上下文内容 |
| event_type | 事件 | string | 事件类型标识 |
| event_data | 事件 | string | 事件原始数据，通常为 JSON 字符串 |
| event_time | 事件 | integer | 事件发生时间（毫秒） |
| event_source | 事件 | string | 事件来源渠道 |
| event_operator | 事件 | string | 事件侧记录的操作人 |
| risk_id | 风险 | string | 风险单唯一 ID |
| event_end_time | 风险 | integer | 风险事件结束时间（毫秒） |
| risk_operator | 风险 | string | 风险单最近操作人 |
| risk_status | 风险 | string | 风险单状态 |
| rule_id | 风险 | integer | 触发的规则 ID |
| rule_version | 风险 | integer | 触发规则版本号 |
| origin_operator | 风险 | string | 风险单最初的处理人 |
| current_operator | 风险 | string | 当前处理人 |
| notice_users | 风险 | string | 通知人员，通常为 JSON 列表 |
| risk_label | 风险 | string | 风险标签（字符串聚合） |
| risk_title | 风险 | string | 风险标题 |
| strategy_tag_ids | 策略标签 | string | 策略绑定的标签 ID JSON 数组 |
| risk_level | 策略 | string | 策略配置的风险等级 |
| is_formal | 策略 | integer | 是否正式策略（1 表示正式） |
| strategy_status | 策略 | string | 策略状态 |

> 提示：`data.results` 会在上述固定字段基础上，根据订阅配置追加额外字段，调用方需要对响应进行动态解析并做好兼容。

# 数据模型

<h2 id="tocS_RiskEventSubscriptionQuerySerializer">RiskEventSubscriptionQuerySerializer</h2>

```json
{
  "token": "string",
  "start_time": 0,
  "end_time": 0,
  "page": 1,
  "page_size": 10
}
```

| 名称 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- |
| token | string | 是 | 订阅 token |
| start_time | integer | 是 | 起始时间（Unix 毫秒时间戳） |
| end_time | integer | 是 | 结束时间（Unix 毫秒时间戳） |
| page | integer | 是 | 页码 |
| page_size | integer | 是 | 每页数量 |

<h2 id="tocS_RiskEventSubscriptionQueryResponse">RiskEventSubscriptionQueryResponse</h2>

```json
{
  "result": true,
  "code": 0,
  "message": "OK",
  "data": {
    "page": 1,
    "page_size": 10,
    "total": 1,
    "results": [
      {
        "event_id": "string",
        "risk_id": "string",
        "strategy_id": 0,
        "risk_level": "string",
        "dtEventTime": "string"
      }
    ],
    "query_sql": "string",
    "count_sql": "string"
  }
}
```

| 名称 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- |
| result | boolean | 是 | 是否成功（true 表示成功，false 表示失败，失败时需结合 code 与 message 分析） |
| code | integer | 是 | 错误码 |
| message | string | 是 | 错误信息 |
| data | object | 是 | 业务数据 |
| data.page | integer | 是 | 当前页码 |
| data.page_size | integer | 是 | 每页数量 |
| data.total | integer | 是 | 总记录数 |
| data.results | array | 是 | 订阅结果列表 |
| data.query_sql | string | 是 | 查询 SQL |
| data.count_sql | string | 是 | 统计 SQL |
