# app_desc.yaml 进程架构设计

## Worker 按 workload 分层

Celery 队列只描述任务的执行特征、资源占用和 SLA，不与 `AIAgentCode` 或具体业务一一对应。新增 Agent 默认复用现有 workload，不增加 Worker、队列和 MQ 连接。

| Workload | Queue / Worker | 适用任务 |
|---|---|---|
| 常规任务 | `celery,default` / `worker` | 字段统计、系统选择、条件检索、风险报告编排等不直接调用 Agent 的任务 |
| 常规 AI | `ai_default` / `ai-default` | 意图识别、会话/报告标题、用户侧分析报告、日志分析、AI 统计、AI 变量预览等 Agent 调用 |
| 单风险报告（兼容） | `risk_single_analyse` / `risk-single` | 策略自动触发、量大的单风险报告模板渲染；保留历史队列和任务级限流 |

`ai-default` 只消费 `ai_default`，通过 `BKAPP_AI_DEFAULT_CONCURRENCY` 调整并发。`risk-single` 只消费兼容队列 `risk_single_analyse`，通过 `BKAPP_RISK_SINGLE_ANALYSE_CONCURRENCY` 调整并发，避免常规 AI 的积压影响高吞吐历史链路。

## Agent 配额与队列解耦

Agent 总配额由公共出站 client 的 Redis 全局限流器按 `AIAgentCode` 控制，跨 Web、Celery、进程和 Pod 共用。`AUDIT_REPORT` 固定 client 默认保留 `risk_single_analyse` 的 Celery `rate_limit`；普通 AI 任务会按请求显式接入全局限流器。

所有 Agent 未配置部署变量时默认使用全局 `10/m`，避免新增 `AIAgentCode` 后因漏配而绕过限流。`BKAPP_AI_AGENT_DEFAULT_RATE_LIMIT` 可调整全局默认值，`BKAPP_AI_<AGENT>_RATE_LIMIT` 可按 Agent 独立覆盖；标题生成、批量分析和 AI 变量预览仍兼容原任务限流环境变量。默认 `10/m` 对齐改造前 `5/m × 2` 个 Worker 副本的总吞吐。

本次为新 Worker 拓扑首次上线，不涉及旧队列存量消息迁移。后续若已上线环境再次调整队列，必须在发布方案中单独设计滚动升级期间的兼容消费和排空步骤。

异步任务遇到限流时由 `AIAgentTask` 进行有 deadline 的延迟 retry；同步请求返回受控 429。限流发生在真实 Agent HTTP 请求之前，因此重试不会重复已发出的调用。

## 新任务接入规则

1. 新增 Agent 异步任务默认使用 `ai_default`；`risk_single_analyse` 仅保留给历史单风险报告链路。
2. 调用 Agent 时传入 `agent_code`；固定 Agent client 在类上声明对应 code。
3. 只有 workload 的隔离需求发生变化时才新增队列或 Worker。

## 其他 Worker

| 进程名 | Queue | 用途 |
|---|---|---|
| `risk-worker` | supervisor 管理 | 风险处理 |
| `notice` | `notice` | 通知发送 |
| `beat` | 无 | 定时任务调度 |
| `gen-risk` | 无 | 风险生成 |
| `log-export` | `log_export` | 日志导出 |
