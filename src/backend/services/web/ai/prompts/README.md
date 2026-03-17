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
