# AI Prompts

AI 服务能力的系统提示词（System Prompt）统一管理目录。

## 目录约定

每个 AI 能力对应一个子目录：

```
prompts/
├── nl2riskfilter/          # 自然语言 → 风险筛选条件
│   ├── generate.py         # 生成脚本（基于 Serializer 动态生成）
│   └── system_prompt.md    # 生成产物（提交到 Git，同步到 aidev 平台）
├── log_analysis/          # 日志分析 Agent 通用约束
│   └── __init__.py         # 人工维护 SYSTEM_PROMPT 常量，调用时直接引用
├── audit_report/           # 风险分析报告（待迁移）
└── ...
```

### 约定

- `generate.py` — 仅在需要从 Serializer、枚举等代码定义生成提示词时提供
- 静态提示词可直接定义为 Python 常量；需要同步平台的生成产物使用 `system_prompt.md`，需提交到 Git
- 有生成脚本的能力修改脚本后重新生成；人工维护的能力不添加额外生成层
- NL2RiskFilter 的系统提示词必须强调模型最终只输出裸 JSON 对象，禁止 Markdown 代码块、解释性文字或前后缀；
  这类格式约束需要同步维护在 `nl2riskfilter/generate.py` 中，不能只手改生成产物

## 使用方式

```bash
cd src/backend

# 生成所有 AI 系统提示词
make prompts

# 只生成 nl2riskfilter
make prompt-nl2riskfilter

# 或直接用 python -m
python -m services.web.ai.prompts.nl2riskfilter.generate
```

NL2RiskFilter 生成后将 `system_prompt.md` 同步到 aidev 平台；日志分析由后端首轮请求注入，见下文。

## 为什么不是纯文本模板？

nl2riskfilter 的 prompt 包含字段表格和枚举值，这些信息直接来源于 `ListRiskRequestSerializer` 和业务常量。
通过脚本动态生成可以确保 prompt 与接口定义始终一致，避免手动维护导致的不同步。

## NL2RiskFilter 上下文输入

`NL2RiskFilter` 用户消息除自然语言查询外，还会透传当前请求人、可用标签、可用策略、当前可用场景 `scenes`
以及当前视角/范围 `scope_type`/`scope_id`。模型需要基于这些上下文将“当前场景”“当前视角”等表达转换为
`ListRiskRequestSerializer` 支持的 `scene_id`、`scope_type`、`scope_id` 等筛选字段。

## NL2RiskFilter 输出格式

模型最终回答必须是 `ListRiskRequestSerializer` 支持的裸 JSON 对象，例如 `{"operator": "zhangsan"}`。
不要输出 Markdown fenced code block（如 ```json）、解释文本、注释、字段说明或其他自然语言内容。
如果无法提取有效筛选条件，返回空对象 `{}`。

## 日志分析 Agent

直接维护 `log_analysis/__init__.py` 中的 `SYSTEM_PROMPT` 常量，无需生成脚本或文件读取。
系统提示词仅定义职责、权限边界与证据可靠性，不指定固定分析维度、报告模板、篇幅或工具调用顺序。
默认分析标准与用户自定义分析指令由任务输入提供，二者不写入这份系统提示词。
日志分析 Task 首轮引用该常量，以 `chat_history` 中的 `role` 消息注入，随后追加本次 `user` 指令；无需在 Agent 平台重复配置。
会话及后续多轮调用约定见 `api/bk_plugins_ai_agent/README.md`。

日志分析首轮 thread_id 复用已持久化的 `Attachment.stream_config.execution_id`，重新执行时轮换；首轮日志记录附件 UID、thread_id 和提示词 SHA-256。后续接续旧会话应保存并复用对应执行的 thread_id。
