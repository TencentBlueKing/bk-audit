# 通用消息规划 Agent 效果评估

本套件验证生产 `MessagePlanningService` 的真实调用链：用户自然语言、当前系统、授权系统及字段上下文一次提交给 AIDev Agent，Agent 返回 `MessagePlan`，后端继续执行 Pydantic、系统白名单与检索条件校验。

## 评估目标

1. 纯系统选择输出 `[SYSTEM_SELECTION]`。
2. 已有有效系统的检索输出 `[LOG_SEARCH]`。
3. 指定新系统并检索输出 `[SYSTEM_SELECTION, LOG_SEARCH]`。
4. 无系统可用于检索时输出 `SYSTEM_REQUIRED` 或 `SYSTEM_UNAVAILABLE`。
5. 闲聊输出 `UNRECOGNIZED_INTENT`。
6. 系统 ID、字段、操作符、枚举值及时间条件能通过后端确定性校验。
7. 相似系统名、提示注入、多值条件和扩展字段场景保持稳定。

Provider 会额外输出 `intent/system_id/condition/error` 兼容字段，便于沿用历史断言；验收主协议是 `outcome/messages/error_code`。`vars.chain` 已不再触发第二次模型调用，历史 chain 用例现在同样验证单 Agent 一次规划。`tests/context-boundaries.yaml` 直接注入生产同构的授权系统字段快照、会话范围和参考时间，用于覆盖空授权、无当前系统、同名系统、深层扩展字段及上下文提示注入。

评测分为两个 profile：

- 首轮能力：`max_attempts=1`，衡量 Agent 第一次输出的准确率，不能被重试掩盖。
- 生产可用性：`max_attempts=3`，与生产任务的解析错误、越权输出和条件语义错误重试预算一致。

Provider 在 metadata 中记录 `attempt_count` 和 `latency_ms`。报告必须同时给出首轮通过率、生产重试后通过率、重试分布和延迟分布。

## AIDev 调用

生产与评测共用以下首轮请求形态：

```json
{
  "chat_history": [
    {"role": "role", "content": "代码仓库中的 SYSTEM_PROMPT"},
    {"role": "user", "content": "本轮完整动态上下文"}
  ],
  "execute_kwargs": {"stream": false, "thread_id": "intent-planning-<uuid>"}
}
```

系统提示词来自 `services/web/ai/prompts/intent_recognition/__init__.py`，不依赖远端 Agent 固定提示词。每个独立规划请求使用新的 `thread_id`。

## 运行

首轮能力基线：

```bash
cd src/backend
PROMPTFOO_PYTHON=.venv/bin/python npx promptfoo eval --no-table \
  -c evals/intent-recognition/promptfooconfig.yaml \
  --env-file .env --no-cache --var max_attempts=1 \
  -o evals/intent-recognition/output/$(date +%Y%m%d)-first-attempt-results.json
```

生产重试基线：

```bash
cd src/backend
PROMPTFOO_PYTHON=.venv/bin/python npx promptfoo eval --no-table \
  -c evals/intent-recognition/promptfooconfig.yaml \
  --env-file .env --no-cache \
  -o evals/intent-recognition/output/$(date +%Y%m%d)-message-plan-results.json
```

`.env` 需要提供 `BKAPP_EVAL_USERNAME` 和 AIDev 调用所需配置。评测输出在 `output/` 下，仅结果文件用于本地分析，不提交凭据或请求正文。稳定性回归可在关键场景上追加 `--repeat 3`；不要只重复整套用例后用总体通过率替代单用例一致性分析。

## 通过标准

- 首轮全量通过率目标不低于 90%，同时记录生产重试后通过率。
- 系统越权、Schema 非法和字段非法必须被后端校验拒绝，不能仅依赖模型自觉。
- 除总体通过率外，记录失败用例、错误类型、尝试次数和延迟分布；重复运行时重点观察相似系统名、复合计划和生产同构上下文边界的一致性。

历史 V1–V6 评测针对旧的 `IntentRecognitionService + NL2JSON` 两段链路，不能与本版本通过率直接比较。本版本结果应建立新的 MessagePlan 基线。
