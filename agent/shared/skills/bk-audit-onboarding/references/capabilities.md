# 公开能力清单与准备依据

## 先诊断，再选配

从本次目标和现有客户端开始，不要求先取得项目源码：

- 记录用户需要前端、后端、版本准备或其他哪类任务，以及当前允许的动作。
- 从客户端已提供的能力列表、技能元数据及连接状态核实可用能力；区分未知、未安装、已安装待验收、已可用、权限不足。不要把未发现直接判成未安装。
- 只检查选中能力的运行环境。可使用当前系统的只读版本/路径查询；没有终端或连接工具时，依据用户提供的信息注明待验收，不伪造执行结果。
- 没有 checkout 时，先形成来源、前提、安装范围和验收计划。执行工程任务时再确认产品 Git 根、当前版本、适用 AGENTS 和下列工程源。

下列源码路径相对产品 checkout；它们是后续任务来源，不是本 onboarding 包的必需文件。产品来源为 [TencentBlueKing/bk-audit](https://github.com/TencentBlueKing/bk-audit)。取得技能前确认所选版本确实包含目标路径，不把默认分支或上游链接当作已安装状态。

## Skills

| 能力与源码位置 | 何时选用 | 准备与验收要点 |
| --- | --- | --- |
| `bk-audit-onboarding`（本包） | 项目上手与能力选配 | 能读取本清单并输出本次计划；不要求安装其他全部能力 |
| `agent/shared/skills/generate-project-commit` | 生成、校验提交消息或实际提交 | 取得该技能并按前后端范围定位规则；准备环境不等于获得提交或推送授权 |
| `agent/shared/skills/bk-audit-version-release` | 准备版本日志与元数据 | 核实版本与范围，按技能声明取得提交技能或产品源；不因选用而发布 |
| `agent/backend/skills/adding-iam-resource-type` | 新增 IAM 资源或排查注册问题 | 产品源码与当前依赖契约在实际实现前必需；不在 onboarding 执行迁移 |
| `agent/backend/skills/ai-eval-suite` | 初始化、运行、分析、调优或重评估 | 按请求选择阶段；分析现有文件不要求模型服务，真实调用另需环境和授权 |
| [Superpowers](https://github.com/obra/superpowers)（外部技能集合） | 当前任务确实需要其设计、调试、评审或验证方法 | 按上游和客户端选择需要的技能，核对工作流约束与项目规则，不整包默认启用 |

技能安装后核对名称、来源/版本、目标客户端与实际目录，确认能发现并读取所需内容；明确的跨技能前提仍需单独核实。角色仅用于筛选能力，不代表所有前端或后端任务都需要同一套技能。

## 工具与运行环境

| 能力 | 当前工程或上游来源 | 采用与检查条件 |
| --- | --- | --- |
| Git、终端及工程运行环境 | 产品 README、`src/backend/README.md`、`src/frontend/package.json` | 执行源码任务时再核对当前分支要求；前后端环境分别判断，不据旧版本号安装 |
| 后端检查与标题工具 | `src/backend/docs/pre-commit.md`、`.pre-commit-config.yaml`（位于 `src/backend`）、`agent/backend/tools/commit-message` | 有后端提交任务时按项目环境验收；不改全局配置，不把安装 hook 作为只读分析前提 |
| 前端构建、lint、类型与提交检查 | `src/frontend/package.json`、ESLint/Stylelint/TypeScript/commitlint 配置 | 核实声明与实际安装情况；部分 lint 带 `--fix`，运行前确认允许修改 |
| skills CLI（可选分发工具） | [官方命令说明](https://github.com/vercel-labs/skills/blob/main/docs/commands.md)与[技能发现规则](https://github.com/vercel-labs/skills/blob/main/docs/creating-skills.md) | 用户选择此方式时核对工具版本要求、来源、目标 Agent 和项目/用户级范围；不是所有任务的必需依赖 |

skills CLI 支持选择单个技能、Git 来源和本地目录；采用已核实的命令，不假定仓库中的任何目录都能被默认发现。单个技能目录含 `SKILL.md` 时可作为明确来源，其他布局按所用版本的发现规则核验。`npx` 在缺少本地包时可能下载并执行包，不用未经确认的 `npx` 调用作无副作用的安装探测。安装前检查所选版本的运行环境要求，不能套用项目自身的 Node 最低版本。

## MCP 接入

MCP 是客户端取得工具能力的一种接入方式，不是业务平台或权限本身。先查看客户端实际暴露的接口，再判断是否需要新增接入。

| 能力与来源 | 何时选用 | 只读验收与边界 |
| --- | --- | --- |
| [Serena](https://github.com/oraios/serena) | 需要代码语义检索和符号操作时，可选 MCP 接入 | 按客户端与上游说明确认项目范围，做获准的只读符号/检索查询；索引和缓存留在本地，修改能力另按任务授权 |
| [Context7](https://github.com/upstash/context7) | 需要查询公开依赖文档时，可选 MCP 接入 | 用公开库名或文档问题核实返回，不发送敏感项目内容，不把文档查询视为业务服务权限 |

已有连接可用就复用。新增连接或认证按客户端及所选来源处理；连接成功后只声明实际验收的能力，不推断提交、模型调用或外部写入已获准。
