# Log Subscription

# Components

## POST Query Subscription Data

> Body Request Parameters

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
        "raw_name": "user_name",
        "field_type": "string"
      },
      "operator": "eq",
      "filters": ["admin"]
    }
  }
}
```

### Request Parameters

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| body | body | [LogSubscriptionQuerySerializer](#schemalogsubscriptionqueryserializer) | Yes | Request body |

> Response Example

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

### Response

| Status Code | Description | Data Model |
| --- | --- | --- |
| 200 | OK | [LogSubscriptionQueryResponse](#schemalogsubscriptionqueryresponse) |

### Response Fields

The returned fields depend on the actual fields of the data source and subscription configuration:

- If `fields` parameter is specified in the request, only the specified fields are returned
- If `fields` parameter is not specified, all fields of the data source are returned (SELECT *)
- Field names and types are determined by the actual table structure in BKBase/Doris

Common field examples:

| Field | Type | Description |
| --- | --- | --- |
| dtEventTimeStamp | integer | Event timestamp (milliseconds) |
| system_id | string | System ID |
| action_id | string | Action ID |
| user_name | string | User name |
| resource_id | string | Resource ID |
| event_content | string | Event content |

> Note: Fields in `data.results` are completely determined by the data source. Callers need to parse according to the actual field structure of the data source.

# Data Models

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
  "filters": {},
  "raw": false
}
```

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| token | string | Yes | Subscription token (UUID format) |
| source_id | string | Yes | Data source unique identifier |
| start_time | integer | Yes | Start time (Unix millisecond timestamp) |
| end_time | integer | Yes | End time (Unix millisecond timestamp) |
| page | integer | Yes | Page number (starts from 1) |
| page_size | integer | Yes | Page size (max 1000) |
| fields | array[string] | No | Specify return field list, empty returns all fields |
| filters | object | No | Custom filter conditions (WhereCondition format, see below) |

### filters Field Description

The `filters` parameter uses `WhereCondition` format to define filter conditions. In the `field` object:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| raw_name | string | Yes | Field name (must match actual field name in data source) |
| field_type | string | Yes | Field type: `string`, `int`, `float`, `timestamp` |

**Simplified Example** (recommended):
```json
{
  "condition": {
    "field": {
      "raw_name": "user_name",
      "field_type": "string"
    },
    "operator": "eq",
    "filters": ["admin"]
  }
}
```

**Full Format Example** (for backward compatibility):
```json
{
  "condition": {
    "field": {
      "raw_name": "user_name",
      "field_type": "string"
    },
    "operator": "eq",
    "filters": ["admin"]
  }
}
```
| raw | boolean | No | Return SQL only without executing query (default false) |

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
    "results": [],
    "query_sql": "string",
    "count_sql": "string"
  }
}
```

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| result | boolean | Yes | Success flag |
| code | integer | Yes | Error code (0 for success) |
| message | string | Yes | Error message |
| data | object | Yes | Business data |
| data.page | integer | Yes | Current page number |
| data.page_size | integer | Yes | Page size |
| data.total | integer | Yes | Total records |
| data.results | array | Yes | Subscription result list |
| data.query_sql | string | Yes | Query SQL (for debugging) |
| data.count_sql | string | Yes | Count SQL (for debugging) |
