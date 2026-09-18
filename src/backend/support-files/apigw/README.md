# 审计 API 网关配置

本目录维护审计服务的 API 网关资源、发布定义与接口文档。

- `definition.yaml`：网关基本信息、发布版本、环境后端地址和 MCP Server 的工具集合。
- `resources.yaml`：对外路径、operationId、请求响应协议、后端映射和鉴权要求。
- `docs/`：接口使用文档。

资源变更通过项目的网关同步发布流程生效；修改定义文件不会立即更新运行中的网关。更新资源时应同步发布版本、后端实现和调用方的接口描述。

## MCP 用户身份与权限

用户态 MCP 工具要求应用认证、用户认证及资源授权，并在后端按当前用户执行数据权限检查。调用方不得通过请求体指定其他用户身份。MCP Server 仅暴露 `resource_names` 声明的工具，工具描述以网关实际发布的 schema 为准。

## 日志分析工具

| operationId | 方法与路径 | 用途 |
| --- | --- | --- |
| `mcp_get_log_field_metadata` | `POST /mcp/logs/field_metadata/` | 探索可查询字段和 JSON 子字段 |
| `mcp_search_logs` | `POST /mcp/logs/search/` | 分页查询已脱敏的日志证据 |
| `mcp_aggregate_logs` | `POST /mcp/logs/aggregate/` | 执行受控统计和分组聚合 |

日志分析工具固定使用默认空间，调用方无需提供 namespace。请求体结构、字段限制及错误码见资源 schema；不要在请求体补入 namespace。升级时调用方应刷新工具定义，原带 namespace 的网关路径不再支持。

明细默认返回包含 event_id 的紧凑证据字段；完整日志和 JSON 字段通过显式投影按需查询。字段探索结果只代表采样，分页明细不能代替总体统计。
