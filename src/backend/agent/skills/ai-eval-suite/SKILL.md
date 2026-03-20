---
name: ai-eval-suite
description: >
  AI 能力评估闭环流程编排工具。基于 promptfoo 驱动"初始化 → 评估 → 分析 → 调优 → 重评估"
  的完整闭环，直到达到用户设定的通过率阈值。当用户提到以下场景时使用此 skill：
  搭建 AI 评估、创建评测套件、运行 promptfoo 评估、分析评估结果、调优 prompt/模型、
  评估不通过需要排查、AI 能力回归测试、对比不同模型表现、评测闭环、benchmark。
  即使用户只是说"跑一下评估""看看哪个模型好""评估挂了""通过率不够""加个模型跑跑"，
  也应该触发此 skill。
---

# AI 评估闭环套件

基于 [promptfoo](https://promptfoo.dev) 的 AI 能力评估闭环流程编排。

**核心价值**：不是"写一个 eval 配置"，而是驱动完整的闭环——从构建评测集到最终达标，
包括失败分析、调优建议、用户确认后执行修改、重评估对比。

## 与官方 promptfoo-evals skill 的关系

```
promptfoo-evals（官方）        ai-eval-suite（本 skill）
────────────────────          ──────────────────────────
"写 eval"                     "跑闭环"
scaffold config/tests         初始化 → 评估 → 分析 → 调优 → 重评估 → 达标
单次任务                       循环流程
promptfoo 语法知识库            引用官方能力，专注流程编排
```

**推荐搭配使用**：初始化 suite（SOP 1）时，优先使用官方
[promptfoo-evals](https://github.com/promptfoo/promptfoo/tree/main/.claude/skills/promptfoo-evals)
skill 来搭建 config / tests / assertions 框架——它是 promptfoo 团队维护的语法知识库，
对配置编写、断言选择、provider 模式等覆盖最全面。

本 skill 在官方能力的基础上补全**评估优化闭环**：分析失败原因、提出调优建议、
驱动重评估直到达标。两者分工互补，官方负责"写得对"，本 skill 负责"跑到过"。

如果用户环境中没有官方 skill，本 skill 的 SOP 1 和 `references/project-structure.md`
中也包含了足够的模板和指引来独立完成初始化。

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


| SOP          | 文件                          | 何时读取         |
| ------------ | --------------------------- | ------------ |
| 1. 初始化 Suite | `references/sop-init.md`    | 用户要创建新的评估套件时 |
| 2. 运行评估      | `references/sop-run.md`     | 需要执行评估时      |
| 3. 分析评估      | `references/sop-analyze.md` | 评估完成后需要分析结果时 |
| 4. 调优        | `references/sop-tune.md`    | 分析发现问题需要修复时  |
| 5. 重评估       | `references/sop-reeval.md`  | 调优后需要验证效果时   |

**子 agent 使用建议**：

| SOP | 步骤 | 子 agent | 原因 |
|-----|------|----------|------|
| SOP 2 | 运行评估 | ✅ 强烈推荐 | 耗时长，无需交互 |
| SOP 3 | 跑分析脚本 | ✅ 推荐 | 机械执行 |
| SOP 3 | 根因分析 | ❌ 主 agent | 需要理解业务上下文 |
| SOP 4 | 调优 | ❌ 主 agent | 需要与用户交互 |
| SOP 5 | 运行+对比 | ✅ 推荐 | 同 SOP 2+3 |

各 SOP 文件顶部有可直接复制的子 agent prompt 模板。

辅助参考：


| 文件                                | 内容                           |
| --------------------------------- | ---------------------------- |
| `references/project-structure.md` | 目录约定、promptfooconfig 模板、命名规范 |
| `references/checklist.md`         | 发布前自检清单                      |


内置脚本：


| 文件                           | 用途                                                                   |
| ---------------------------- | -------------------------------------------------------------------- |
| `scripts/bk_llm_provider.py` | 蓝鲸 LLM 网关 provider（OpenAI 标准协议），可作为 LLM-as-Judge grader 或独立 provider |
| `scripts/analyze_results.py` | 评估结果分析：失败分类、两轮纵向对比、多模型横向对比 |


## 快速判断：用户处于哪个阶段？


| 用户说的话                           | 对应 SOP  | 动作                 |
| ------------------------------- | ------- | ------------------ |
| "给 XX 能力搭建评估" / "创建评测套件"        | SOP 1   | 读 `sop-init.md`    |
| "跑一下评估" / "运行 benchmark"        | SOP 2   | 读 `sop-run.md`     |
| "评估结果怎么样" / "哪些用例失败了"           | SOP 3   | 读 `sop-analyze.md` |
| "怎么修" / "调一下 prompt" / "换个模型试试" | SOP 4   | 读 `sop-tune.md`    |
| "加个模型对比一下" / "用 XX 模型也跑一下"     | SOP 4   | 读 `sop-tune.md`（优先级 3） |
| "改完了再跑一次" / "对比一下前后"            | SOP 5   | 读 `sop-reeval.md`  |
| "评估不通过" / "通过率太低" / "评估挂了"      | SOP 3   | 读 `sop-analyze.md` |
| "还是不行" / "通过率没变"                | SOP 3→4 | 重新分析 + 调优          |
| "从头到尾跑一遍"                       | SOP 1-5 | 按顺序执行              |


## 公共 Provider 体系

评估中有两类 provider 需要区分：

```
evals/providers/            ← 公共 provider（跨 suite 复用）
  bk_llm_provider.py        ← 蓝鲸 LLM 网关（LLM-as-Judge / 独立调用）

evals/<suite>/providers/    ← 业务 provider（走完整业务链路）
  provider.py               ← 调用真实业务接口
```

- **业务 provider** 每个 suite 自己编写，直接调用业务 API，走完整链路
- **公共 provider** 放在 `evals/providers/`，各 suite 通过 `python:../providers/xxx.py` 引用
- 使用 `llm-rubric` 等模型辅助断言时，必须通过 `defaultTest.options.provider` 指定 grader，
避免依赖 promptfoo 默认的 OpenAI key

蓝鲸项目初始化时，可将本 skill 内置的 `scripts/bk_llm_provider.py` 复制到 `evals/providers/`
作为 LLM-as-Judge 的 grader provider。详见 `references/sop-init.md` Step 3。

## 核心约束

这些规则贯穿所有 SOP，不可违反：

1. **环境变量无敏感默认值** — 用户名、密钥等必须从环境变量获取，不允许硬编码
2. **不自建 wrapper 脚本** — 直接使用 `npx promptfoo` CLI，避免额外抽象层增加调试复杂度
3**每个环节产出必须持久化** — 评估结果（JSON/HTML）、分析结论（conclusion.md）、调优决策（README 调优记录）、迭代进展（README 进展表）都要落地到文件，不能只停留在对话中

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
  ⚠️ 必须通过 defaultTest.options.provider 指定 grader provider
```

