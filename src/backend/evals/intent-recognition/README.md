# 意图 Agent 按需上下文评测

本套件在本地加载 Django、生产 `MessagePlanningService` 的 system/user/retry 提示词、MessagePlan 解析与授权校验，
沿用 `.env` 配置的 BKOP 意图 Agent 地址，以非流式请求获取最终输出，条件继续经过 `ConditionAssemblyService`。
不另建本地 Agent，也不要求非流式接口没有的 MCP 中间轨迹。模型和工具选择由当前环境的 Agent 执行。

## 输入与判尺

用户提示词只提供本轮原话、可信会话阶段、当前系统、授权系统 ID 和时间锚点。
系统详情、字段、操作和资源类型由 Agent 按需求调用它绑定的 `audit-meta` 获取，不提前塞入 Prompt。
`audit-meta` 由四个系统元数据工具与二期 `mcp_get_log_field_metadata` 组成，不向意图 Agent 提供明细或聚合能力。

评测只观察最终选择效果：

- `outcome/messages/error_code` 协议、系统 ID 和消息序列正确。
- 系统范围、字段和条件经后端独立校验；错误结果不得混成有效检索。
- 关键用例比较完整条件集合和时间窗，操作人、JSON 路径等不能遗漏或多加。
- 单值 `include/eq`、`exclude/neq` 按查询语义等价比较；保留路径顺序、值类型和大小写。
- 覆盖系统切换、已选系统检索、未选系统、闲聊、注入、多字段、多级 JSON 与授权边界。
- 时间覆盖任意合法月份、分钟的动态标记和首轮准确绝对范围；不要求返回工具调用轨迹，不增加多轮条件继承。

Provider 额外输出 `intent/system_id/condition/error` 兼容历史断言。
默认校验字段覆盖完整生产标准字段；校验失败记录 `diagnostic.final_plan` 与结构化错误，便于回查最终输出。
泛义失败使用非零条件；旧Web的 `-1` 反选标记不能作为AI条件中的字面失败值。
`authorized_systems` 等合成字段夹具只用于最终后端校验，不会注入 Agent 上下文；`vars.chain` 不触发第二个 Agent。
涉及系统名称或隐藏元数据的用例，必须在远端 MCP 有对应可访问数据才能作为效果结论。
仓库中的合成系统不代表 BKOP 中存在同名系统；环境数据不匹配须单独分类，不可恢复预加载来掩盖问题。
真实环境适配数据放在 Git 忽略目录，禁止把真实账号、系统或日志写入测试代码。

## 运行

复用项目已有 promptfoo，不自动安装或升级。以下命令在 `src/backend` 执行：

```bash
PROMPTFOO_PYTHON="$PWD/.venv/bin/python" npx --no-install promptfoo validate \
  -c evals/intent-recognition/promptfooconfig.yaml

PROMPTFOO_PYTHON="$PWD/.venv/bin/python" npx --no-install promptfoo eval --no-table \
  -c evals/intent-recognition/promptfooconfig.yaml --env-file .env --no-cache \
  --max-concurrency 2 --var max_attempts=1 \
  -o evals/intent-recognition/output/first-attempt-results.json
```

`.env` 需有 `BKAPP_EVAL_USERNAME` 和现有意图 Agent 路由、鉴权配置。
默认沿用平台配置的模型；仅在已有明确模型对照需求时填写 provider.config.model。
本地 Python、Agent URL 和凭据解析与生产同源，不需要另配 LLM 网关或升级 AIDev SDK。
模型正文的用户固定为 `eval_actor`，真实账号只用于鉴权。输出目录保持 Git 忽略。

先用 `--filter-pattern` 或 `--filter-first-n` 做小集冒烟，不导出正式结论；
正式运行覆盖确认范围并用 `-o` 归档。默认 `max_attempts=1` 衡量首轮能力；
生产纠错评测追加 `--var max_attempts=3` 并单独归档，不能混为同一通过率。
重试携带上一轮输出和结构化校验错误，超时或服务异常重放原请求。

## 分析与验收

首轮全量目标通过率不低于 90%；系统越权、非法字段和协议错误仍必须被后端拒绝。
记录环境/Agent、范围、版本、通过率、错误类型、attempt_count 与 latency_ms；
非流式未提供的模型内部轮次、token 和工具轨迹不推测、不补造。
先区分连接/鉴权、远端工具配置、环境数据差异、模型决策与判尺问题，再判断下一步。
本地运行不代表已发布网关工具或完成 Agent 平台绑定，部署后需另行验收。

历史预加载上下文和两段式链路的通过率不能直接比较，本版本建立按需上下文的新基线。
