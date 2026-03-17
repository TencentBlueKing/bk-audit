---
name: ai-eval-suite
description: >
  AI 能力评估闭环流程编排工具。基于 promptfoo 驱动"初始化 → 评估 → 分析 → 调优 → 重评估"
  的完整闭环，直到达到用户设定的通过率阈值。当用户提到以下场景时使用此 skill：
  搭建 AI 评估、创建评测套件、运行 promptfoo 评估、分析评估结果、调优 prompt/模型、
  评估不通过需要排查、AI 能力回归测试、对比不同模型表现、评测闭环、benchmark。
  即使用户只是说"跑一下评估"或"看看哪个模型好"，也应该触发此 skill。
---

# AI 评估闭环套件

基于 [promptfoo](https://promptfoo.dev) 的 AI 能力评估闭环流程编排。

**核心价值**：不是"写一个 eval 配置"，而是驱动完整的闭环——从构建评测集到最终达标，
包括失败分析、调优建议、用户确认后执行修改、重评估对比。

## 与官方 promptfoo-evals 的关系

```
promptfoo-evals（官方）        ai-eval-suite（本 skill）
────────────────────          ──────────────────────────
"写 eval"                     "跑闭环"
scaffold config/tests         初始化 → 评估 → 分析 → 调优 → 重评估 → 达标
单次任务                       循环流程
promptfoo 语法知识库            引用官方能力，专注流程编排
```

初始化 suite 时，参考官方 `promptfoo-evals` skill 的 cheatsheet 来编写 config/tests/assertions。
如果用户环境中有该 skill，优先使用其能力来生成配置。本 skill 专注于闭环流程中官方不覆盖的部分：
**分析失败原因、提出调优建议、驱动重评估直到达标**。

## SOP 五步闭环

```
SOP 1        SOP 2        SOP 3        SOP 4        SOP 5
初始化  ──→  运行评估  ──→  分析评估  ──→  调优  ──→  重评估
  │                                       ↑            │
  │                                       └────────────┘
  │                                        未达标时循环
  └─ 通过率阈值（用户设定）                  达标 → 归档
```

每个 SOP 的详细操作指南在 `references/` 目录下，按需读取：

| SOP | 文件 | 何时读取 |
|-----|------|---------|
| 1. 初始化 Suite | `references/sop-init.md` | 用户要创建新的评估套件时 |
| 2. 运行评估 | `references/sop-run.md` | 需要执行评估时 |
| 3. 分析评估 | `references/sop-analyze.md` | 评估完成后需要分析结果时 |
| 4. 调优 | `references/sop-tune.md` | 分析发现问题需要修复时 |
| 5. 重评估 | `references/sop-reeval.md` | 调优后需要验证效果时 |

辅助参考：

| 文件 | 内容 |
|------|------|
| `references/project-structure.md` | 目录约定、promptfooconfig 模板、命名规范 |
| `references/checklist.md` | 发布前自检清单 |

## 快速判断：用户处于哪个阶段？

| 用户说的话 | 对应 SOP | 动作 |
|-----------|---------|------|
| "给 XX 能力搭建评估" / "创建评测套件" | SOP 1 | 读 `sop-init.md` |
| "跑一下评估" / "运行 benchmark" | SOP 2 | 读 `sop-run.md` |
| "评估结果怎么样" / "哪些用例失败了" | SOP 3 | 读 `sop-analyze.md` |
| "怎么修" / "调一下 prompt" / "换个模型试试" | SOP 4 | 读 `sop-tune.md` |
| "改完了再跑一次" / "对比一下前后" | SOP 5 | 读 `sop-reeval.md` |
| "从头到尾跑一遍" | SOP 1-5 | 按顺序执行 |

## 核心约束

这些规则贯穿所有 SOP，不可违反：

1. **环境变量无敏感默认值** — 用户名、密钥等必须从环境变量获取，不允许硬编码
2. **不创建 mock provider** — 评估必须调用真实 AI 服务
3. **不自建 wrapper 脚本** — 直接使用 `npx promptfoo` CLI
4. **配置文件顶部必须有 JSON Schema 声明** — `# yaml-language-server: $schema=https://promptfoo.dev/config-schema.json`
5. **output 目录 git 忽略** — 评估结果仅本地存储
6. **运行命令统一格式** — `--env-file .env --no-cache`
7. **断言优先级** — 确定性断言 > 相似度断言 > 模型辅助断言

## 断言选择速查

```
确定性断言（快、免费、稳定）  →  优先使用
  contains / icontains / regex / is-json / python / javascript
    ↓ 不够用时
相似度断言（较快、便宜）
  similar / rouge-n / bleu
    ↓ 仍不够用时
模型辅助断言（慢、花钱、有波动）  →  慎用
  llm-rubric / factuality / context-faithfulness
```
