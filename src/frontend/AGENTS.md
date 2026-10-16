# AGENTS.md

蓝鲸审计中心前端（`bk-audit/src/frontend`）的 Agent 入口。对话用简体中文。


## 项目速览

- 单包前端：Vue 3.5 + TypeScript + Vite 8 + vue-router 4 + vue-i18n 11 + `bkui-vue`（新增列表优先 `tdesign-list`，存量 `render-list` 继续复用）。无 Pinia / Vuex。
- 包管理器 **npm**（Node `>= 16.16.0`）。常用：`npm run dev`（默认 `https://localhost:8082`）、`npm run type-check`、`npm run build`。
- 分层：`views` → `components` / `hooks` / `utils` → `domain`（service → source → model）→ `@utils/request`。视图只 import `@service/*`。
- 状态：URL query 为主（筛选/分页/场景），辅以 sessionStorage / localStorage / mitt。场景三元组见 `utils/assist/scene-system-params.ts`。
- 提交：Husky + lint-staged（前端）；message 以仓库根 `src/backend/agent/skills/generate-project-commit` 为准。禁止提交 `.agents/`、`skills-lock.json`、`.env*`。

## 行为

- 先方案后改代码（琐碎单文件除外）。不确定就问，不猜接口或权限。
- 未经同意不主动修 eslint / stylelint / 格式，不擅自跑构建或长脚本。
- `git commit` / `push` 前展示范围与 message，等明确确认。禁止 `--no-verify`、`push --force`。
- 收尾用 `memory-save` 判断是否记经验；架构/模块变化再改 `docs/`，不要把密钥写入文档或 learnings。
- 图标优先查 `@lib/bk-icon`：在 `lib/bk-icon/iconcool.json` 的 `icons[].name` 里检索，用全局 `AuditIcon` 的 `type` 对上该 name。不要只查 bkui Icon 文档就断定没有。库里确实没有，再记入交付报告「icon 缺口」，不要用近似图标、emoji 或手写图形冒充已还原。

## 任务路由

先按意图读对应 skill（路径：`.agents/skills/<name>/SKILL.md`），再按需打开 `docs/`。

| 意图 | 读 |
| --- | --- |
| 配环境 / 装 skill / TAPD·Figma MCP | `bk-audit-onboarding`（只配环境，不写业务） |
| TAPD 单据、分支、commit、PR、回写 | `blueking-tapd-dev`；写查见其 `write-check.md` |
| Figma 还原 | `blueking-figma-dev` |
| 颜色 / 圆角 / 字号 | `bk-audit-theme`（`--audit-*`，`src/css/tokens.css`） |
| bkui / 区间日期 / 列表表格 | `bkui-vue-components` / `blueking-date-picker` / `blueking-tdesign-ui` |
| 改完代码审查 | `code-reviewer`（分层见其 `frontend-conventions.md`） |
| TAPD 验收、测试矩阵、评论草稿 | `test-agent`（不落盘测试文件、不直接写 TAPD） |
| 是否记经验 | `memory-save`（写 skills 源仓，不写产品仓 `.agents` 副本） |

项目知识（人读、也对 Agent 开放，**不要做成第二套 skill**）：

| 要找什么 | 打开 |
| --- | --- |
| 文档地图 | `docs/README.md` |
| 目录、别名、启动 | `docs/architecture.md` |
| 导航、角色、模块在哪 | `docs/feature-map.md`、`docs/business-modules.md` |
| 风险/策略/接入怎么转 | `docs/business-flows.md` |
| 公共组件（含全局注册） | `docs/components.md` |
| hooks、request、场景参数 | `docs/hooks-and-utils.md` |
| 新增接口、service 清单 | `docs/domain-layer.md` |
| 路由 meta、列表骨架、常用命令 | `docs/conventions.md` |

写页面时：新增列表优先 `tdesign-list`；存量 `render-list` 页继续复用，不要在业务页裸铺表格。有权限点用 `AuthButton`；侧栏优先 `AuditSideslider`。模块清单、接口清单以 `docs/` 为准，过时了改文档，不要把百科抄进本文件。
