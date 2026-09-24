# app_desc.yaml 进程架构设计

## Worker 分层策略

所有 Celery Worker 按任务特征分为两层：

### 第一层：default Worker（通用任务）

- **进程名**：\`worker\`
- **Queue**：\`celery,default\`
- **并发模型**：gevent, 128 并发
- **适用任务**：
  - 纯 CPU/IO 的短平快任务（如字段统计 \`generate_field_statistics\`）
  - 调用 AI 但耗时短（<30s）的任务（如意图识别、NL2JSON）
  - 新接入的常规异步任务默认投递到此 Worker，无需单独建队列

### 第二层：audit-ai Worker（AI 专用）

- **进程名**：\`audit-ai\`
- **Queue**：\`ai_title,risk_single_analyse,risk_multi_analyse,risk_report,ai_assistant_log_analysis,ai_assistant_statistics\`
- **并发模型**：gevent, 128 并发（环境变量 \`BKAPP_AUDIT_AI_CONCURRENCY\` 可调）
- **关键参数**：\`--prefetch-multiplier=1\`（避免长任务预取堆积）
- **适用任务**：
  - 调用 LLM 的长任务（流式输出、分钟级耗时）
  - 风险分析（单条/批量）、风险报告生成、AI 标题生成
  - 日志分析、统计分析等 AI 能力

## 设计决策

### 为什么将多个 AI Queue 合并到一个 Worker？

1. **限流天然隔离**：Celery 的 \`rate_limit\` 是按 **task name x worker instance** 独立计算的，不是按 queue 计算。即使所有 AI 任务跑在同一个 Worker 里，各任务的限流互不干扰
2. **资源利用率**：所有 AI 任务的核心都是"调用 LLM API 等待 IO 返回"，非常适合 gevent 协程复用。拆分多个 Worker 会导致大量协程槽位空闲
3. **运维简化**：从 6 个 Worker 组（12 实例）缩减为 1 个 Worker 组（2 实例），资源节省 ~70%

### 为什么保留多个 Queue 名称？

- 保留 queue 名称是为了**部署灵活性**：未来如果某个 AI 能力需要独立扩缩容，只需新增一个 Worker 监听对应 queue 即可，无需修改任何 task 代码

### 新任务接入规则

| 任务特征 | 投递目标 | 示例 |
|---------|---------|------|
| 纯 CPU/IO，不调 AI | \`default\` queue | 字段统计、ES 检索 |
| 调 AI 但短平快（<30s） | \`default\` queue | 意图识别、NL2JSON |
| 调 AI 且长任务（流式/分钟级） | 对应 AI queue | 风险分析、日志分析 |

## 其他 Worker 说明

| 进程名 | Queue | 用途 | 备注 |
|--------|-------|------|------|
| \`risk-worker\` | - | 风险处理（supervisord 管理） | 独立进程，非 Celery |
| \`notice\` | \`notice\` | 通知发送 | 低频，1 副本 |
| \`beat\` | - | 定时任务调度 | 单副本 |
| \`gen-risk\` | - | 风险生成 | 独立命令 |
| \`log-export\` | \`log_export\` | 日志导出 | 低频，1 副本 |
