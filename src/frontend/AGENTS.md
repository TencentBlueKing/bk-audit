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
- 收尾用 `bk-audit-memory-save` 判断是否记经验；架构/模块变化再改 `docs/`，不要把密钥写入文档或 learnings。
- 图标优先查 `@lib/bk-icon`：在 `lib/bk-icon/iconcool.json` 的 `icons[].name` 里检索，用全局 `AuditIcon` 的 `type` 对上该 name。不要只查 bkui Icon 文档就断定没有。库里确实没有，再记入交付报告「icon 缺口」，不要用近似图标、emoji 或手写图形冒充已还原。

## 任务路由

先按意图读对应 skill（路径：`.agents/skills/<name>/SKILL.md`），再按需打开 `docs/`。

开发类任务（TAPD 链接或单号，或要求实现、修改、修复页面、联调、按设计稿做功能）先读 `bk-audit-dev-flow`。本地没有这个 skill 时，按下面的表逐个读取，并在回复里标明哪些关没有证据，不能写成流程已完成。

| 意图 | 读 |
| --- | --- |
| 开发类任务总控 | `bk-audit-dev-flow` |
| 配环境 / 装 skill / TAPD·Figma MCP | `bk-audit-onboarding`（只配环境，不写业务） |
| TAPD 单据、分支、commit、PR、回写 | `bk-audit-tapd-dev`；写查见其 `write-check.md` |
| UI 页面 / 组件开发（有无 Figma 均可） | `bk-audit-ui-development` |
| 颜色 / 圆角 / 字号 | `bk-audit-theme`（`--bk-theme-*`，`src/css/tokens.css`） |
| 界面规范 | `bk-audit-ui-conventions`（只读 `.agents/skills` 这份） |
| 数据说明书 | `bk-audit-data-spec` |
| bkui / 区间日期 / 列表表格 | `bk-audit-bkui-vue` / `bk-audit-date-picker` / `bk-audit-tdesign-ui` |
| 改完代码审查 | `bk-audit-code-reviewer`（分层见其 `frontend-conventions.md`） |
| TAPD 验收、测试矩阵、评论草稿 | `bk-audit-test-agent`（不落盘测试文件、不直接写 TAPD） |
| 交付前测试闭环 | `bk-audit-development-test`（影响分析、vitest、执行前审查，页面层调用 `bk-audit-ui-verification`） |
| 页面验收：视觉 / Figma 对齐、交互对齐、联调、修复复验 | `bk-audit-ui-verification`（只用 BrowserOS neo，自动执行不中途询问；不使用 Playwright / aitest） |
| 开 worktree | `bk-audit-worktree` |
| 是否记经验 | `bk-audit-memory-save`（写 skills 源仓，不写产品仓 `.agents` 副本） |

浏览器验收只用 BrowserOS neo，入口地址读 `.ui-workflow/browser-origin.txt`（一行 origin，git 忽略；worktree 由 `bk-audit-worktree` 生成）。不要运行 `npx skills add ./node_modules/@tencent/aitest`，那会把已移除的 Playwright 流程和 rule 装回来。

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

改全局样式时顺带同步主题 profile：改了 `src/css/tokens.css`（含场景层 `@scene` 注册）、`reset.css`、`common.css`、`src/css/theme/*`（含 `scenes.css`），或在 `main.ts` 新增全局样式文件，先把新文件加进 `.agents/skills/bk-audit-theme/references/profile/profile.json`（token 文件进 `tokenSources`，公共样式进 `publicStyleSources`），再在前端目录运行 `node scripts/check-theme-tokens.mjs` 和 `python3 .agents/skills/bk-audit-theme/references/profile/build_profile.py --root "$PWD"`，重新生成 token 表、公共样式表和场景表（worktree 共享 `.agents` 软链，必须带 `--root`）。新增或调整视觉场景按 `bk-audit-theme` 的 `scene-workflow.md`。本地没有这个 skill 时跳过。开发态验证只消费生成结果，不维护主题规则。


绝对禁止敏感信息提交

- 当触发commit和推送时，必须严格检查是否存在敏感信息提交，一旦发现或者不确定是否敏感的情况，立即终止告知。
