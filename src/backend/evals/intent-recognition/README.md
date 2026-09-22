# 通用消息规划 Agent 效果评估

本套件验证生产 `MessagePlanningService` 的真实调用链：用户自然语言、会话阶段、授权系统摘要、公共标准字段及当前系统详情一次提交给 AIDev Agent，Agent 返回 `MessagePlan`，后端再按目标系统执行 Pydantic、权限和检索条件校验。

## 评估目标

1. 纯系统选择输出 `[SYSTEM_SELECTION]`。
2. 已有有效系统的检索输出 `[LOG_SEARCH]`。
3. 指定新系统并检索输出 `[SYSTEM_SELECTION, LOG_SEARCH]`。
4. 无系统可用于检索时输出 `SYSTEM_REQUIRED` 或 `SYSTEM_UNAVAILABLE`。
5. 闲聊输出 `UNRECOGNIZED_INTENT`。
6. 系统 ID、字段、操作符、枚举值及时间条件能通过后端确定性校验。
7. 相似系统名、提示注入、多值条件和扩展字段场景保持稳定。
8. 用户明确表达多级拓展路径时，Agent 能基于公共 `extend_data` 容器生成 `extend_data + keys` 条件，并在“完整路径已发现”和“仅父节点及样例已发现”两类目标系统快照上通过后端校验。
9. 拓展字段类型或操作符不明确时，Agent 可结合用户表达和样例在查询 Schema 的全局枚举内选择；采样元数据不作为错误的强限制。

Provider 会额外输出 `intent/system_id/condition/error` 兼容字段，便于沿用历史断言；验收主协议是 `outcome/messages/error_code`。`vars.chain` 已不再触发第二次模型调用，历史 chain 用例现在同样验证单 Agent 一次规划。`tests/context-boundaries.yaml` 中的 `authorized_systems` 同时提供授权摘要和后端校验快照；只有 `current_system_id` 对应系统的字段差异和拓展字段受控样例会进入 Agent 上下文，普通标准字段运行时样例不进入 Prompt。没有当前系统时，Agent 只看到授权摘要和公共字段，目标系统快照用于计划产出后的确定性校验。`tests/nested-extension-fields.yaml` 固定覆盖两种目标快照与两种用户表达组成的四格矩阵，并严格断言消息序列、操作人、完整嵌套路径、值和默认近一天时间窗；`tests/invalid-conditions.yaml` 验证意图已识别但操作符不受支持时稳定返回 `INVALID_CONDITION`。

评测分为两个 profile：

- 首轮能力：`max_attempts=1`，衡量 Agent 第一次输出的准确率，不能被重试掩盖。
- 生产可用性：`max_attempts=3`，与生产任务的解析错误、越权输出和条件语义错误重试预算一致。纠错轮次会携带上一轮完整输出和结构化校验错误；AIDev 超时或服务异常只重放原始请求。

Provider 在 metadata 中记录 `attempt_count` 和 `latency_ms`。报告必须同时给出首轮通过率、生产重试后通过率、重试分布和延迟分布。

## AIDev 调用

生产与评测共用以下首轮请求形态：

```json
{
  "chat_history": [
    {"role": "role", "content": "代码仓库中的 SYSTEM_PROMPT_TEMPLATE"},
    {"role": "user", "content": "本轮完整动态上下文"}
  ],
  "execute_kwargs": {"stream": false, "thread_id": "intent-planning-<uuid>"}
}
```

系统提示词和用户提示词都定义在 `services/web/ai/prompts/intent_recognition/templates.py` 的独立多行字符串模板中，运行时只注入强类型上下文和 `MessagePlan` Schema，不执行本地文件读取，也不依赖远端 Agent 固定提示词。每个独立规划请求使用新的 `thread_id`。

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

评测夹具中的人员、系统及样例路径统一使用 `eval_*` 或“示例”前缀的合成值。`BKAPP_EVAL_USERNAME` 只用于 AIDev 接口鉴权，模型上下文中的用户固定为 `eval_actor`，避免真实账号进入评测请求正文。

## 通过标准

- 首轮全量通过率目标不低于 90%，同时记录生产重试后通过率。
- 系统越权、Schema 非法和字段非法必须被后端校验拒绝，不能仅依赖模型自觉。
- 除总体通过率外，记录失败用例、错误类型、尝试次数和延迟分布；重复运行时重点观察相似系统名、复合计划和生产同构上下文边界的一致性。

历史 V1–V6 评测针对旧的 `IntentRecognitionService + NL2JSON` 两段链路，不能与本版本通过率直接比较。本版本结果应建立新的 MessagePlan 基线。
