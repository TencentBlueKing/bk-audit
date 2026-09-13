# 项目总览

> [← 文档索引](./README.md) ｜ 下一篇：[架构与目录](./architecture.md)

## 代码规模

| 指标 | 数值 |
| --- | --- |
| 源码总行数（`src/`） | 约 207,700 行 |
| Vue 单文件组件 | 584 |
| TypeScript 文件 | 275（含 `.tsx`） |
| 业务模块（`views/`） | 20（`tool-manage-shared` 无独立路由） |
| 公共组件（`components/`） | 35 个顶层目录；`main.ts` 全局注册 23 个 |
| 组合式函数（`hooks/`） | 27 |
| 领域服务（`domain/service/`） | 29 |
| 领域模型（`domain/model/`） | 23 个目录 |

## 技术选型

| 维度 | 选型 |
| --- | --- |
| 框架 | Vue 3.5（已开启 `defineModel`）+ TypeScript 5.2 |
| 构建 | Vite 8（含 `@vitejs/plugin-vue-jsx`、`vite-plugin-monaco-editor`、`@vitejs/plugin-basic-ssl`） |
| 路由 | vue-router 4.2（history 模式，单文件路由表） |
| 国际化 | vue-i18n 11（`src/language/lang/zh.js` / `en.js`） |
| UI 库 | `bkui-vue` 2.0（主）+ `@blueking/tdesign-ui`（部分列表） |
| 重型控件 | `monaco-editor`、`@vueup/vue-quill`（富文本）、`echarts` 5、`xlsx`、`sortablejs`、`vuedraggable` |
| 蓝鲸生态 | `@blueking/login-modal`、`@blueking/bk-user-selector`、`@blueking/notice-component`、`@blueking/date-picker`、`@blueking/platform-config` |
| 状态管理 | 无集中式 store，见「状态管理策略」 |
| 网络 | 自研 `@utils/request`（axios 封装） |
| 监控 | Aegis（TAM 前端监控）、页面水印、Agent 预热 |
| 规范 | ESLint（`eslint-config-tencent`）+ Stylelint + Commitlint（conventional）+ Husky + lint-staged |

## 状态管理策略

项目不使用集中式状态库，全局状态由四种载体分担：

| 载体 | 存放内容 |
| --- | --- |
| `sessionStorage` | `BK_AUDIT_CONFIG`（启动配置）、`userRole`（角色数组）、`userScenePermission`（场景权限原始布尔）、列表分页记忆 |
| `localStorage` | 场景/系统选择（`scene-system-selector:selected`）、表格列设置、最近使用人员 |
| **URL query** | 筛选条件、分页、排序、时间范围、场景上下文（`scene_id` / `scope_id` / `scope_type`） |
| `mitt` 事件总线 | 跨组件事件：`permission-page`、`permission-catch`、`show-notice` |

> **核心约定「URL 即状态」**：`use-url-search` 负责读写 URL，`use-record-page` 负责列表分页记忆，二者配合让所有列表状态可分享、可刷新恢复。

## 工程能力

| 能力 | 实现 |
| --- | --- |
| 国际化 | `vue-i18n`，中英双语；公共文案 `src/language/lang/`，模块文案 `src/views/<模块>/language/`，由 `src/language/index.js` 合并 |
| 主题变量 | `src/css/tokens.css`（设计变量）+ `reset.css` + `common.css` |
| 指令 | `v-cursor`（`src/directives/cursor/`）、`v-bk-tooltips`（来自 bkui-vue） |
| 前端监控 | Aegis，按 `config.aegis_id` 启用，上报接口与静态资源测速 |
| 页面水印 | `utils/assist/water-mark.ts`，按 `EntryManageService.watermark()` 返回启用 |
| Agent 预热 | `utils/assist/ping-agent.ts`，登录后按 `config.agent_auth.agents` 预热，失败不阻断 |
| 服务端 | `server/index.js`（Express 静态服务），`npm run build-server` 用 esbuild 打包 |

---

> [← 文档索引](./README.md) ｜ 下一篇：[架构与目录](./architecture.md)
