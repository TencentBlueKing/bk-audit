# 跨端能力

| 任务 | 入口 | 用途 |
| --- | --- | --- |
| 项目探索与能力维护 | [bk-audit-onboarding](skills/bk-audit-onboarding/SKILL.md) | 定位当前 checkout，选择探索或维护入口 |
| 生成、校验或提交改动 | [generate-project-commit](skills/generate-project-commit/SKILL.md) | 按前端、后端或混合范围选择检查与 hook |
| 准备版本日志和元数据 | [bk-audit-version-release](skills/bk-audit-version-release/SKILL.md) | 固定发布范围，在 notes 分支准备可合入 main 的改动 |

## 可选工具与方法

| 来源 | 用途与采用条件 |
| --- | --- |
| [Serena](https://github.com/oraios/serena) | 代码语义检索与符号操作；索引和缓存留在本地 |
| [Context7](https://github.com/upstash/context7) | 公开依赖文档查询；不发送敏感项目内容 |
| [Superpowers](https://github.com/obra/superpowers) | 设计、调试、评审和验证方法；选用前核对其工作流约束与项目规则 |

Serena、Context7 可通过 MCP 接入，具体方式按客户端与上游说明选择。采用外部技能前检查许可、脚本和触发条件。
