---
name: ai-eval-suite
description: 当用户需要搭建 AI 评估、运行 benchmark、对比模型表现、或排查评估失败时使用。
---

# AI 评估闭环套件

基于 [promptfoo](https://promptfoo.dev) 的 AI 能力评估闭环流程编排。

审计后端场景中，SOP 示例的 project-root 指产品 checkout 的 src/backend，而非仓库根或技能安装目录；从该目录定位 .venv、evals 与项目配置。

可单独用于初始化、运行、分析、调优或重评估，也可按请求组合为闭环。只执行用户要求的阶段；完成该阶段后报告结果与可选下一步，不因未达标自动修改或继续调用模型。完整闭环也须约定迭代次数或资源预算。

工具优先使用项目已有版本；安装依赖、真实模型试跑与平台操作按当前请求处理，不因读取 SOP 自动执行。

初始化 suite（SOP 1）可参考
[promptfoo-evals](https://github.com/promptfoo/promptfoo/tree/main/.claude/skills/promptfoo-evals)
中的 config、tests、assertions 和 provider 用法；本技能补充项目场景与结果分析。

如果用户环境中没有官方 skill，本 skill 的 SOP 1 和 `references/project-structure.md`
中也包含了足够的模板和指引来独立完成初始化。

## 可组合的评估阶段

每个 SOP 的详细操作指南在 `references/` 目录下，按需读取：


| SOP          | 文件                          | 何时读取         |
| ------------ | --------------------------- | ------------ |
| 1. 初始化 Suite | `references/sop-init.md`    | 用户要创建新的评估套件时 |
| 2. 运行评估      | `references/sop-run.md`     | 需要执行评估时      |
| 3. 分析评估      | `references/sop-analyze.md` | 评估完成后需要分析结果时 |
| 4. 调优        | `references/sop-tune.md`    | 分析发现问题需要修复时  |
| 5. 重评估       | `references/sop-reeval.md`  | 调优后需要验证效果时   |

环境支持且任务允许时，可将独立评估运行并行处理；不把子 agent 作为必需依赖。

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
| "还是不行" / "通过率没变"                | SOP 3   | 分析原因，再按修改授权决定是否调优 |
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
3. **结果可追溯** — 执行评估时保留结果文件与配置/版本信息；分析与调优决策按当前请求和项目约定留存，复用已有记录，不为未执行的阶段创建材料

## 断言选择速查

```
确定性断言
  contains / icontains / regex / is-json / python / javascript
    ↓ 
语义相似度断言
  similar / rouge-n / bleu
    ↓ 
模型辅助断言
  llm-rubric / factuality / context-faithfulness
  ⚠️ 必须通过 defaultTest.options.provider 指定 grader provider
```
