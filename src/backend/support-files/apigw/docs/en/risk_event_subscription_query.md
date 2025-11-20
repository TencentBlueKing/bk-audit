# Risk Event Subscription

# Components

## POST Query Subscription Data

> Body Parameters

```json
{
  "token": "xxxx-xxxx-xxxx-xxxx",
  "start_time": 1700000000000,
  "end_time": 1700600000000,
  "page": 1,
  "page_size": 10
}
```

### Request Parameters

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| body | body | [RiskEventSubscriptionQuerySerializer](#schemariskeventsubscriptionqueryserializer) | Yes | Request payload |

> Response Example

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

### Response

| Status Code | Description | Data Model |
| --- | --- | --- |
| 200 | OK | [RiskEventSubscriptionQueryResponse](#schemariskeventsubscriptionqueryresponse) |

### Return Field Details

grouped by event, risk, strategy, and tag information:

| Field | Category | Type | Description |
| --- | --- | --- | --- |
| dtEventTime | Event | string | Formatted event time such as `YYYY-MM-DD HH:mm:ss` |
| dtEventTimeStamp | Event | integer | Event timestamp in milliseconds |
| event_id | Event | string | Unique event ID |
| event_content | Event | string | Full event content (raw TEXT) |
| raw_event_id | Event | string | Raw event ID used to join risk/strategy tables |
| strategy_id | Event | integer | Alert strategy ID |
| event_evidence | Event | string | Evidence or context captured by the event |
| event_type | Event | string | Event type identifier |
| event_data | Event | string | Original event payload, usually a JSON string |
| event_time | Event | integer | Occurrence time in milliseconds |
| event_source | Event | string | Source channel of the event |
| event_operator | Event | string | Operator recorded on the event side |
| risk_id | Risk | string | Risk ticket ID |
| event_end_time | Risk | integer | Event end time in milliseconds |
| risk_operator | Risk | string | Latest operator on the risk ticket |
| risk_status | Risk | string | Risk ticket status |
| rule_id | Risk | integer | Triggered rule ID |
| rule_version | Risk | integer | Triggered rule version |
| origin_operator | Risk | string | Initial handler of the risk ticket |
| current_operator | Risk | string | Current handler |
| notice_users | Risk | string | Notified users, typically a JSON list |
| risk_label | Risk | string | Aggregated risk labels |
| risk_title | Risk | string | Risk title |
| strategy_tag_ids | Strategy tag | string | JSON array of tag IDs bound to the strategy |
| risk_level | Strategy | string | Risk level configured in the strategy |
| is_formal | Strategy | integer | Whether the strategy is formal (1 means yes) |
| strategy_status | Strategy | string | Strategy status |

> Note: `data.results` may include additional columns beyond the list above depending on subscription configuration. Consumers must parse the payload dynamically and remain backward compatible.

# Schemas

<h2 id="schemariskeventsubscriptionqueryserializer">RiskEventSubscriptionQuerySerializer</h2>

```json
{
  "token": "string",
  "start_time": 0,
  "end_time": 0,
  "page": 1,
  "page_size": 10
}
```

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| token | string | Yes | Subscription token |
| start_time | integer | Yes | Start timestamp (Unix ms) |
| end_time | integer | Yes | End timestamp (Unix ms) |
| page | integer | Yes | Page number |
| page_size | integer | Yes | Page size |

<h2 id="schemariskeventsubscriptionqueryresponse">RiskEventSubscriptionQueryResponse</h2>

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

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| result | boolean | Yes | Whether the call succeeds (true = success, false = failure; inspect code/message when false) |
| code | integer | Yes | Error code |
| message | string | Yes | Error message |
| data | object | Yes | Payload |
| data.page | integer | Yes | Current page number |
| data.page_size | integer | Yes | Page size |
| data.total | integer | Yes | Total count |
| data.results | array | Yes | Subscription result list |
| data.query_sql | string | Yes | Query SQL |
| data.count_sql | string | Yes | Count SQL |
