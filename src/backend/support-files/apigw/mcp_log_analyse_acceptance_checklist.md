# 审计日志分析 MCP 上线与授权验收清单

状态：PENDING。本文仅记录待执行的上线验收步骤，不表示任何环境已经发布或授权成功。

- Agent code：`bp-ai-log-analyse`
- 目标环境：`stag`、`prod`
- 目标应用：由发布负责人在执行时填写，不写入代码仓库的密钥或令牌。
- MCP Server：`audit-log-analysis`，由 `definition.yaml` 在部署时同步到 APIGW MCP。
- 允许的 operationId：`mcp_get_log_field_metadata`、`mcp_search_logs`、`mcp_aggregate_logs`

## 发布前

- 确认网关定义版本为 `0.0.15`，资源变更说明包含“新增审计日志分析 MCP 工具”。
- 确认 `stag`、`prod` 的 `audit-log-analysis.resource_names` 均精确绑定上述三项工具。
- 确认 Agent 仅关联上述三个 operationId，未关联其他日志工具或通配资源。
- 分别在 `stag` 与 `prod` 记录发布单、执行人和时间。

## 授权验证

- 使用目标应用调用三个 operationId，记录三次成功响应的 `request_id`，并确认业务结果位于标准 envelope 的 `data`。
- 使用未授权应用分别调用三个 operationId，确认均被网关拒绝，并记录状态码和 `request_id`。
- 在网关和 Agent 配置中复核没有额外 operationId 可见或可调用。
- 将环境、目标应用、验收证据和结论回填到发布工单；全部完成前保持本清单状态为 PENDING。
