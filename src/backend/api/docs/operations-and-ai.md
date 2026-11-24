# 监控、安全、可视化与 AI API

返回：[API 明细索引](README.md) · [授权总览](../../docs/api_authorization.md)

以下是代码声明的 HTTP 方法与相对路径，未拼接网关环境地址。身份、状态的读法见索引。

模块：[BKMonitor 监控平台](#bk_monitor) · [BKSEC 风险接入](#bk_sec) · [BKSEC 发单插件](#bk_sec_send_plugin) · [BKVision 可视化](#bk_vision) · [DevSecOps 水印](#watermark) · [通用 AI Agent](#bk_plugins_ai_agent) · [AI 审计报告](#bk_plugins_ai_audit_report) · [AI 审计分析](#bk_plugins_ai_audit_analyse)

## bk_monitor

**BKMonitor 监控平台** · [接口定义](../bk_monitor/default.py)

常规 API 多租户用 `BKAPP_BK_MONITOR_APIGW_NAME` 的 `prod`，单租户按 `BKAPP_USE_APIGW` 决定网关或
ESB。告警策略读／写、通知组查询、告警查询与集群元数据分开核对。自定义指标／事件走 `BKAPP_BK_MONITOR_METRIC_PROXY_URL` 并提交
data_id／通道 token，单独配通道而非套用常规网关权限。

| Resource              | 方法   | 相对路径或配置项                                                              | 审计侧身份 | 已见引用                                            |
|-----------------------|--------|-------------------------------------------------------------------------------|------------|-----------------------------------------------------|
| `SearchAlarmStrategy` | `POST` | 单 `/search_alarm_strategy_v3/`；多 `/app/alarm_strategy/search/`             | 平台       | 待确认                                              |
| `SaveAlarmStrategy`   | `POST` | 单 `/save_alarm_strategy_v3/`；多 `/app/alarm_strategy/save/`                 | 平台       | [代码](../../services/web/analyze/controls/bkm.py)  |
| `DeleteAlarmStrategy` | `POST` | 单 `/delete_alarm_strategy_v3/`；多 `/app/alarm_strategy/delete/`             | 平台       | [代码](../../services/web/analyze/controls/bkm.py)  |
| `SwitchAlarmStrategy` | `POST` | 单 `/switch_alarm_strategy/`；多 `/app/alarm_strategy/switch/`                | 平台       | [代码](../../services/web/analyze/controls/bkm.py)  |
| `UnifyQuery`          | `POST` | 单 `/time_series/unify_query/`；多 `/app/data_query/time_series_unify_query/` | 平台       | 待确认                                              |
| `GetVariableValue`    | `POST` | 单 `/get_variable_value/`；多 `/app/data_query/get_variable_value/`           | 平台       | 待确认                                              |
| `SearchNoticeGroup`   | `POST` | 单 `/search_notice_group/`；多 `/app/user_group/search/`                      | 平台       | [代码](../../services/web/entry/handler/healthz.py) |
| `SaveNoticeGroup`     | `POST` | 单 `/save_notice_group/`；多 `/app/user_group/save/`                          | 平台       | 待确认                                              |
| `DeleteNoticeGroup`   | `POST` | 单 `/delete_notice_group/`；多 `/app/user_group/delete/`                      | 平台       | 待确认                                              |
| `SearchAlert`         | `POST` | 单 `/search_alert/`；多 `/app/alert/search/`                                  | 平台       | [代码](../../services/web/risk/handlers/bkm.py)     |
| `GetClusterInfo`      | `GET`  | 单 `/metadata_get_cluster_info/`；多 `/app/metadata/get_cluster_info/`        | 平台       | [代码](../../services/web/query/utils/elastic.py)   |
| `ReportMetric`        | `POST` | `/v2/push/`                                                                   | 通道 Token | [代码](../../core/monitor.py)                       |
| `ReportEvent`         | `POST` | `/v2/push/`                                                                   | 通道 Token | [代码](../../core/monitor.py)                       |

## bk_sec

**BKSEC 风险接入** · [接口定义](../bk_sec/default.py)

`BKAPP_BKSEC_API_URL` 优先，默认按 `BKAPP_BKSEC_APIGW_NAME` 生成地址。该模块直接继承
SDK，不走审计统一租户头注入；个人风险类型与平台风险类型即使路径相同也不是同一种身份。按部署功能和 Mock 开关实际判定是否外调。

| Resource                   | 方法   | 相对路径或配置项                      | 审计侧身份 | 已见引用                                           |
|----------------------------|--------|---------------------------------------|------------|----------------------------------------------------|
| `ProjectChoices`           | `GET`  | `/api/v1/project/choices/`            | 个人       | [代码](../../services/web/risk/resources/bksec.py) |
| `RiskAccessList`           | `GET`  | `/api/v1/risk/risk_access/`           | 个人       | [代码](../../services/web/risk/bksec/service.py)   |
| `RiskAccessListAsPlatform` | `GET`  | `/api/v1/risk/risk_access/`           | 平台       | [代码](../../services/web/risk/bksec/service.py)   |
| `PreviewTicketFields`      | `POST` | `/api/v1/risk/preview_ticket_fields/` | 个人       | [代码](../../services/web/risk/bksec/service.py)   |

## bk_sec_send_plugin

**BKSEC 发单插件** · [接口定义](../bk_sec_send_plugin/default.py)

由 `BKAPP_BKSEC_PLUGIN_CONFIG_API_URL` 提供完整接入地址；使用独立插件应用凭据（成对配置时）或 SDK 默认认证。和上面的 BKSEC
项目／风险接口分开申请。

| Resource       | 方法   | 相对路径或配置项 | 审计侧身份         | 已见引用                                       |
|----------------|--------|------------------|--------------------|------------------------------------------------|
| `ConfigUpsert` | `POST` | 配置的完整 URL   | 插件应用／SDK 默认 | [代码](../../services/web/risk/bksec/rules.py) |

## bk_vision

**BKVision 可视化** · [接口定义](../bk_vision/default.py)

单租户使用 `BKAPP_BK_VISION_API_URL` 或网关名构造地址；多租户 `BKAPP_BK_VISION_API_NAME` 的 `prod`
。视图／Dataset、订阅写入与分享权限接口分开核对；分享列表未配置平台鉴权。

| Resource               | 方法     | 相对路径或配置项                               | 审计侧身份 | 已见引用                                             |
|------------------------|----------|------------------------------------------------|------------|------------------------------------------------------|
| `QueryMeta`            | `GET`    | `/api/v1/meta/query/`                          | 平台       | [代码](../../services/web/tool/tasks.py)             |
| `GetPanel`             | `GET`    | `/api/v1/panel/`                               | 平台       | 待确认                                               |
| `QueryData`            | `POST`   | `/api/v1/datasource/query/`                    | 平台       | 待确认                                               |
| `QueryVariableData`    | `POST`   | `/api/v1/variable/query/`                      | 平台       | [代码](../../services/web/vision/handlers/query.py)  |
| `QueryDataset`         | `POST`   | `/api/v1/dataset/query/`                       | 平台       | [代码](../../services/web/vision/handlers/query.py)  |
| `QueryFieldData`       | `POST`   | `/api/v1/field/{uid}/preview_data/`            | 平台       | [代码](../../services/web/vision/handlers/query.py)  |
| `CreateReportStrategy` | `POST`   | `/api/v1/report/create_report_strategy/`       | 平台       | [代码](../../apps/meta/handlers/system_diagnosis.py) |
| `UpdateReportStrategy` | `PUT`    | `/api/v1/report/update_report_strategy/{uid}/` | 平台       | [代码](../../apps/meta/handlers/system_diagnosis.py) |
| `DeleteReportStrategy` | `DELETE` | `/api/v1/report/delete_report_strategy/{uid}/` | 平台       | [代码](../../apps/meta/handlers/system_diagnosis.py) |
| `GetShareList`         | `GET`    | `/api/v1/share/get_share_list/`                | SDK 默认   | [代码](../../services/web/vision/resources.py)       |
| `CheckShareAuth`       | `GET`    | `/api/v1/share/check_share_auth/`              | 平台       | [代码](../../services/web/tool/permissions.py)       |
| `QueryTestVariable`    | `POST`   | `/api/v1/variable/test/`                       | 平台       | [代码](../../services/web/vision/handlers/query.py)  |

## watermark

**DevSecOps 水印** · [接口定义](../watermark/default.py)

`BKAPP_DEVSECOPS_APIGW_NAME`；仅使用对应水印功能时纳入申请。

| Resource            | 方法   | 相对路径或配置项         | 审计侧身份 | 已见引用                                      |
|---------------------|--------|--------------------------|------------|-----------------------------------------------|
| `GenerateWatermark` | `POST` | `/web/api/v1/watermark/` | SDK 默认   | [代码](../../services/web/entry/resources.py) |

## bk_plugins_ai_agent

**通用 AI Agent** · [接口定义](../bk_plugins_ai_agent/default.py)

按 Agent Code 动态选择网关；相同路径不代表相同网关权限。路由优先级：`BKAPP_AI_{AGENT}_API_URL` →
`BKAPP_AI_{AGENT}_APIGW_NAME` → 默认网关名（`prod`）。以 Agent
专属或全局应用凭据调用，不将用户身份当作网关认证。参见 [Agent Code](../ai_agent_codes.py)
与 [运行说明](../bk_plugins_ai_agent/README.md)。

| Resource         | 方法   | 相对路径或配置项                            | 审计侧身份 | 已见引用                                                        |
|------------------|--------|---------------------------------------------|------------|-----------------------------------------------------------------|
| `ChatCompletion` | `POST` | `/bk_plugin/openapi/agent/chat_completion/` | 应用       | [代码](../../services/web/ai_assistant/services/title_agent.py) |

## bk_plugins_ai_audit_report

**AI 审计报告** · [接口定义](../bk_plugins_ai_audit_report/default.py)

固定审计报告 Agent，复用通用请求及流式链路；单独核对报告 Agent 的网关和应用凭据。

| Resource         | 方法   | 相对路径或配置项                            | 审计侧身份 | 已见引用                                            |
|------------------|--------|---------------------------------------------|------------|-----------------------------------------------------|
| `ChatCompletion` | `POST` | `/bk_plugin/openapi/agent/chat_completion/` | 应用       | [代码](../../services/web/risk/report/providers.py) |

## bk_plugins_ai_audit_analyse

**AI 审计分析** · [接口定义](../bk_plugins_ai_audit_analyse/default.py)

固定审计分析 Agent，地址由 `BKAPP_AI_AUDIT_ANALYSE_API_URL` 或 `BKAPP_AI_AUDIT_ANALYSE_APIGW_NAME` 解析到该 Agent 网关。

| Resource         | 方法   | 相对路径或配置项                            | 审计侧身份 | 已见引用                                 |
|------------------|--------|---------------------------------------------|------------|------------------------------------------|
| `ChatCompletion` | `POST` | `/bk_plugin/openapi/agent/chat_completion/` | 应用       | [代码](../../services/web/risk/tasks.py) |
