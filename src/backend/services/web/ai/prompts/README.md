# AI Prompts

AI 服务能力的系统提示词（System Prompt）统一管理目录。

## 目录约定

每个 AI 能力对应一个子目录：

```
prompts/
├── nl2riskfilter/          # 自然语言 → 风险筛选条件
│   ├── generate.py         # 生成脚本（基于 Serializer 动态生成）
│   └── system_prompt.md    # 生成产物（提交到 Git，同步到 aidev 平台）
├── audit_report/           # 风险分析报告（待迁移）
└── ...
```

### 约定

- `generate.py` — 生成脚本，负责从代码定义（Serializer、枚举等）动态生成 prompt
- `system_prompt.md` — 生成产物，即实际的系统提示词，**需提交到 Git**
- 修改 prompt 时，编辑 `generate.py` 中的模板，然后重新生成
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

生成后将 `system_prompt.md` 的内容同步到 aidev 平台对应的 Agent 配置中。

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
