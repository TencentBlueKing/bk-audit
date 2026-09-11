# AI 助手平台可观测性与稳定性

本文面向 AI 助手平台运维、监控策略配置人员和维护开发者，说明
`services.web.ai_assistant` 的 SLO、BKM 策略和故障处置方法。

本文只维护部署运行所需的观测口径，不复制代码协议或内部执行流转：

- Metric/Event 名称、字段、单位和维度以
  [`observability.py`](../services/web/ai_assistant/observability.py) 的声明式子类为准；
- AI 助手配置的环境变量、默认值、单位和直接行为以
  [`services/web/settings.py`](../services/web/settings.py) 为准；
- BKM 共享数据源和监控上报任务配置以
  [`config/default.py`](../config/default.py) 为准。
- 平台可观测性架构、生命周期和 Handler 接入约束见
  [`services/web/ai_assistant/docs/observability.md`](../services/web/ai_assistant/docs/observability.md)。

## 1. 职责边界

本模块保障以下平台链路：

- 异步 Message、Attachment 从创建到 `SUCCESS`/`FAILED` 的最终收敛；
- Worker 丢失、Broker 重投或异常退出后，长期 `PROCESSING` 对象的发现和自动失败；
- 流式 Attachment 的 Redis 实时通道、MySQL 快照归档和最终结果收敛；
- 平台生命周期 Metric、Event、Trace 和结构化日志；
- BKM 仪表盘、告警策略和故障处置依据。

以下内容不由本模块评价：Agent 内容质量、日志检索准确率、A2UI 协议质量、浏览器
RUM、通用 HTTP/MySQL/Redis/RabbitMQ 健康。它们继续复用项目已有 APM 和基础设施监控。


## 2. SLO 与时间口径

| 对象 | 滚动 28 天目标 | 活动告警线 | 自动失败线 |
| --- | --- | --- | --- |
| 异步 Message | 99.5% 在创建后 2 分钟内进入终态 | 5 分钟无活动 | 15 分钟无活动 |
| 异步 Attachment | 99.5% 在创建后 30 分钟内进入终态 | 1 小时无活动 | 2 小时无活动 |

终态是 `SUCCESS` 或 `FAILED`。各时间字段口径如下：

- 排队耗时：Worker 已启动时为 `started_at - queued_at`；Worker 从未启动便进入终态时为
  `finished_at - queued_at`；同步执行缺少 `queued_at` 时为 0；
- 当前执行耗时：`finished_at - started_at`；
- 总收敛耗时：`finished_at - created_at`；
- 失活时长：`now - last_activity_at`。

手动重试复用原对象，因此总收敛耗时仍从首次 `created_at` 计算；它会生成新
`task_id` 并重置当前执行的排队、开始、活动和结束时间。Celery 自动重试、
`self.retry()` 和 RabbitMQ 重投属于同一次平台执行，保留首次开始时间并刷新活动时间。
SLO 超时不直接终止仍有 checkpoint 的长任务；只有 `last_activity_at` 达到硬失效线才自动失败。
Handler 的 Retry `countdown/eta` 必须小于对应对象的自动失败线；平台不持久化待重试 ETA，
超过硬失效阈值的延迟重试会按失活执行收敛，后续到达的旧投递由 fencing 忽略。

## 3. Metric

所有 Metric 均通过 `core.monitor.Metric` 最佳努力异步上报，投递失败不改变
业务状态。四个指标组的完整字段、单位和维度说明见
[`AIAssistantExecutionMetric`](../services/web/ai_assistant/observability.py)、
`AIAssistantProcessingMetric`、`AIAssistantStreamExecutionMetric` 和
`AIAssistantReconcileMetric` 声明。

BKM 配置只需维护以下运维口径：

- **Execution**：只统计赢得终态 CAS 的对象。SLO 达标率为
  `sum(ai_assistant_execution_slo_met_count) / sum(ai_assistant_execution_count)`；
  成功率和失败率按 `status` 维度聚合 `ai_assistant_execution_count`；
  排队、执行和总收敛耗时使用对应 duration Metric 计算 P50/P95/P99。
- **Processing**：每轮巡检开始时在 MySQL 聚合，并按
  `object_type + business_type + age_bucket` 展示扫描时存量；当轮随后自动失败的对象
  仍计入该样本，用于表达巡检实际发现的积压。`UNKNOWN` 只观测活动时间异常对象，
  不用于自动失败。
- **Stream Execution**：每个流 execution 收敛时上报一次。降级率和截断率分别为
  `sum(ai_assistant_stream_degraded_count) / sum(ai_assistant_stream_execution_count)` 和
  `sum(ai_assistant_stream_truncated_count) / sum(ai_assistant_stream_execution_count)`；
  事件数与字节数只用于容量趋势，不根据单个事件告警。
- **Reconcile**：每轮巡检结束上报心跳和处理结果；告警使用心跳缺失、
  巡检耗时和自动失败数判断兜底任务是否可用。

## 4. Event

Event 用于少量、可定位且需要人工处理的异常。普通 Handler 失败、正常 Retry、
旧任务 fencing 和单次 Redis 降级不产生 Event。Event 的 `target/context/extra`
字段协议以 [`AIAssistantExecutionTimeoutEvent`](../services/web/ai_assistant/observability.py)
等子类注释为准。

| Event name | 告警意图 | 维护动作 |
| --- | --- | --- |
| `ai_assistant_execution_timeout` | 发现平台已自动收敛的长期失活执行 | 查对象 Trace、Worker 和依赖，判断容量不足、依赖阻塞或 Handler 活动刷新缺失 |
| `ai_assistant_reconcile_failed` | 发现失活执行兜底任务不可用 | 恢复数据库/Redis/Celery 后确认心跳，并检查故障窗口内的过期存量 |
| `ai_assistant_invariant_violation` | 发现 Handler 输出或平台终态契约被破坏 | 阻止问题版本扩散，按 `target` 和 Trace 定位契约实现 |

对象 UID、task ID 仅进入 Event target/extra，用于受控排查，不进入 Metric 维度。

## 5. Trace 与日志

业务 Span：

- `ai_assistant.message.execute`：Message Task 完整执行；
- `ai_assistant.attachment.execute`：Attachment Task 完整执行；
- `ai_assistant.attachment.stream`：流执行最终归档或 Retry 刷盘的收敛阶段；
- `ai_assistant.execution.reconcile`：一轮 Message/Attachment 巡检。

允许的结构化字段包括 `object_type`、`object_uid`、`business_type`、`task_id`、
`execution_id`、`stage`、`status`、`error_code`、`retry_kind`、`duration_ms`。
应用结构化日志禁止记录 `input_data`、`context_data`、`output_data`、`stream_archive`、
日志样例和流事件正文。项目 OTel 当前会按通用策略记录异常信息；Handler 不应在异常
正文中拼接敏感输入或日志数据，涉及敏感依赖时应先在业务边界转换为受控异常。

## 6. 环境配置

完整环境变量、默认值和单项行为见上文引用的 settings 源码。生产调整必须保持：

- Message 和 Attachment 均满足 `SLO < WARNING < FAILURE`；SLO 从创建时间计算，
  Warning/Failure 从当前执行最近活动时间计算；
- `AI_ASSISTANT_RECONCILE_TIME_LIMIT_SECONDS < AI_ASSISTANT_RECONCILE_INTERVAL_SECONDS`，
  避免巡检正常执行时发生重叠调度；
- Stream 的单事件、事件数、Redis 字节和 MySQL 归档字节上限相互独立，
  调整前必须先通过容量 Metric 确认实际瓶颈；
- Stream 活动持久化间隔应显著小于 Attachment 的 Failure 阈值，确保持续发送
  业务事件的长任务不会被巡检误判失活。

事故止损时，优先设置
`BKAPP_AI_ASSISTANT_RECONCILE_AUTO_FAIL_ENABLED=false`：继续扫描和上报，但不修改对象。
只有巡检本身持续影响系统时才设置 `BKAPP_AI_ASSISTANT_RECONCILE_ENABLED=false`。
配置变更后按项目部署方式重启 Celery Beat/Worker，并确认 BKM 心跳恢复。

## 7. BKM 仪表盘

建议手工建立以下面板：

1. Message/Attachment 终态成功率、失败率和滚动 28 天 SLO 达标率；
2. 排队、当前执行、总收敛耗时 P50/P95/P99；
3. PROCESSING 存量和 `HEALTHY/WARNING/EXPIRED/UNKNOWN` 年龄分布；
4. 自动失败数量，按对象类型和业务类型分组；
5. 流执行降级率、截断率、事件数量和字节趋势；
6. 巡检心跳、耗时、扫描量、过期量和自动失败量。

## 8. 告警策略

建议最多配置六类核心告警。初始阈值需根据环境基线调整，但不能取消最小样本、
持续时间和恢复条件。

| 策略 | 建议条件 | 恢复条件 |
| --- | --- | --- |
| Message SLO | 近 30 分钟终态样本 >= 20，2 分钟内收敛率低于 99.5%，持续 10 分钟 | 连续 15 分钟 >= 99.5% |
| Attachment SLO | 近 2 小时终态样本 >= 10，30 分钟内收敛率低于 99.5%，持续 30 分钟 | 连续 30 分钟 >= 99.5% |
| 批量硬超时 | 同一 `object_type+business_type` 10 分钟自动失败 >= 5 | 连续 20 分钟无新增批量超时 |
| 巡检不可用 | 心跳连续 5 分钟缺失，或 `reconcile_failed` 持续出现 | 连续 5 个周期心跳正常且无失败事件 |
| 平台约束异常 | 任一 `invariant_violation` | 对应版本修复并连续 30 分钟无新增 |
| 流式持续降级 | 30 分钟流执行样本 >= 10，降级率 >= 5%，持续 15 分钟 | 连续 30 分钟降级率 < 1% |

通知组、策略 ID 和仪表盘 ID 与环境相关，仅在 BKM 管理，不写入应用配置。
样例数据不纳入告警和 SLO 面板，过滤值以样例上报命令中的声明为准。

## 9. Runbook

### 9.1 执行超时

1. 从 Event target 获取对象 UID，查询对象 `task_id`、`business_type`、
   `started_at`、`last_activity_at` 和错误码；
2. 按 task ID 查 `*.execute` Trace 和 Worker 日志；
3. 判断是否为 Worker 容量、依赖阻塞或 Handler 在硬失效线之外运行且没有平台活动；
4. 若存在正常任务误杀，立即关闭自动失败，不关闭扫描；
5. 修复后由用户使用现有手动重试恢复，平台不自动重新投递 FAILED 对象。

### 9.2 巡检心跳缺失

1. 检查 Celery Beat 是否注册 `monitor_ai_assistant_executions`；
2. 检查默认队列 Worker、Redis 短锁和数据库连接；
3. 查 `ai_assistant_reconcile_failed` Event 与 `ai_assistant.execution.reconcile` Trace；
4. 恢复后确认连续 5 个周期心跳，并检查故障窗口内 EXPIRED 存量是否已收敛。

### 9.3 平台约束异常

1. 按 Event 的对象类型、业务类型、错误码和 target 定位 Handler；
2. 对照该类型 Pydantic 输出模型检查返回值；
3. 确认对象没有被错误写为 SUCCESS；
4. 补契约测试后修复，不通过放宽平台校验绕过问题。

### 9.4 流式持续降级

1. 区分 `degraded_count` 与 `truncated_count`；
2. 降级优先检查 Redis 写入、MySQL checkpoint 和事件发送速率；
3. 截断检查单事件、事件数、Redis 字节和 MySQL 归档上限；
4. MySQL 最终 `output_data` 成功时，实时流丢失不等于最终产物失败；
5. 只有获得真实容量基线后才调整上限，禁止直接把事件正文加入监控。
