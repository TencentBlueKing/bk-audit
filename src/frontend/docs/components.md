# 公共组件

> [← 文档索引](./README.md) ｜ 上一篇：[核心业务流程](./business-flows.md) ｜ 下一篇：[Hooks 与工具函数](./hooks-and-utils.md)

`src/components/` 共 **35** 个顶层目录。下表按可复用封装列出（`auth/` 拆成 5 种形态）。`main.ts` 全局注册 **23** 个组件：本目录 22 个（★）+ `@blueking/date-picker` 的 `DatePicker`。使用 ★ 组件无需 import。

## 分类清单

| 分类 | 组件 |
| --- | --- |
| 表单与编辑 | ★`audit-form` · ★`select-verify` · `editor`（Quill）· `rich-editor` · `editor-image-preview` · `edit-box` · `application-parameter` |
| 列表与检索 | ★`render-list` · ★`tdesign-list` · ★`search-box` · `risk-export-button` |
| 布局与导航 | ★`audit-router-view` · `keep-alive-router-view` · `audit-navigation` · `audit-menu` · ★`smart-action` · `router-back` · ★`scroll-faker` · `statement-sidebar` |
| 权限 | ★`auth-button` · ★`auth-component` · ★`auth-switch` · ★`auth-option` · ★`auth-router-link` · ★`apply-permission`（全局名 `ApplyPermissionCatch`） |
| 选择器 | `audit-user-selector` · ★`audit-user-selector-tenant` · `ip-selector`（+`selector-box`）· `scene-system-selector` |
| 展示与反馈 | ★`audit-icon` · ★`skeleton-loading` · `show-tooltips-text` · `version-log` · `multiple-line-clamp` · ★`render-sensitivity-level` · ★`relation-ship` · ★`audit-popconfirm` · ★`audit-collapse-panel` · ★`audit-sideslider` |

## 表单与编辑类

| 组件 | 职责与实现要点 |
| --- | --- |
| **audit-form** ★ | `bk-form` 包装。① `validate()` 失败时把首个 `.is-error` 项 `scrollIntoView`；② 通过根节点 click 监听 + `watch(model, deep)` 判定用户是否真实编辑过，编辑后置 `window.changeConfirm = true`（配合路由离开确认）；③ 统一 label 字号 12px。expose `validate()` / `clearValidate()`。**带表单的页面统一使用它而非裸 bk-form。** |
| **select-verify** ★ | 给任意选择器加「必填校验」红框 + 告警图标。expose `getValue()` / `clearFields()`。 |
| **editor** | Quill 富文本（`content-type="html"`），用于报告与处理意见。粘贴统一走 `DOMPurify.sanitize`，base64 图片先上传再替换为远端 URL；自定义 `report-table-blot` 支持插入表格并识别粘贴网格；`fullscreenScope` 三态（`viewport` / `main` / `parent`）；自动将文本 URL 转超链接；`maxLen` 硬截断。 |
| **rich-editor** | 代码/富文本编辑器（禁用态展示），props：`default` / `disabled` / `height` / `enableTable`。 |
| **editor-image-preview** | 编辑器内图片预览（旋转 / 缩放 / 切换）。 |
| **edit-box/tag.vue** | 标签/数组只读展示，超出折叠 + 一键复制。 |
| **application-parameter** | 风险处理/通知类「应用参数」编辑器，支持从风险字段插入变量占位符（子件 `rule-index.vue`）。 |

## 列表与检索类

| 组件 | 职责与实现要点 |
| --- | --- |
| **render-list** ★ | bk-table 版远程分页列表（存量配置类页面：策略 / 规则 / 通知组 / 联表 / 处理套餐 / 事件 / 系统列表等）。远程分页（`remote-pagination`）、URL 分页/排序恢复（旧 `order_field/order_type` 与新 `sort:['-event_time']` 双向兼容）、按视口高度计算 `page_size`（`isUserSelectedPageSize` 避免覆盖用户选择）、排序图标高亮恢复、场景参数注入、`useRecordPage` 分页记忆。expose：`fetchData` / `resetFetchData`（切场景清空排序筛选并强制重挂载）/ `refreshList` / `getListData`。**改这些页时继续复用本封装，不要无故换成裸表或回退选型。** |
| **tdesign-list** ★ | TDesign 版远程分页列表。**新增列表优先使用**。在 render-list 能力基础上额外提供 `selection-change`、`getSelectionMeta`、`resolveSelectedRowKeys`、`getExportFilters`，支持**跨页全选**与批量导出；prop `is-need-scene-params` 控制场景参数注入。已用于风险五视图、工具列表、场景管理、平台报表等。不要在业务页再铺一套裸 `PrimaryTable`。 |
| **search-box** ★ | 风险/事件检索统一入口。`fieldConfig` 驱动；`render-key`（关键词检索）与 `render-value`（字段值检索）两种形态通过 keep-alive 切换并写入 URL `searchType`；首屏从 URL 反序列化筛选条件，提交时回写；时间范围支持相对量（如 `now-6M`）；内置 `risk-export-button` 并 expose `exportData(riskIds, type, {async, filters})`。 |
| **risk-export-button** | 风险批量导出按钮。只负责 UI 与并发互斥，导出逻辑由父组件 `exportFn` 注入；全局单例 `isRiskExportLoading` 保证同一时刻只有一个导出任务，期间 disabled 并显示 loading。 |

## 布局与导航类

| 组件 | 职责与实现要点 |
| --- | --- |
| **audit-router-view** ★ | 「权限 + 路由」门面：监听事件总线 `permission-page`，收到则渲染 `apply-permission/page.vue`，否则渲染 `keep-alive-router-view`。 |
| **keep-alive-router-view** | 按 `route.meta.keepAlive` 在 `<keep-alive>` 与非缓存 `<component>` 间二选一，key 取 `meta.keepAliveKey \|\| route.name`（支持同路由多实例）。新页面要缓存只需在 router meta 打 `keepAlive: true`。 |
| **audit-navigation** | 全站布局骨架：顶栏 + 可折叠侧栏 + 滚动内容区 `#auditNavigationContent`。插槽：`logo` / `header` / `headerRight` / `side` / `headerTips` / `nodeSideContent`；emit `menu-flod`。 |
| **audit-menu** | 侧边导航菜单（index / item / item-group），通过 `provide(menuKey)` 共享 `activeIndex` 与 `floded`；emit `change(index)`。 |
| **smart-action** ★ | 底部操作栏自动吸底。`getBoundingClientRect` 判断 placeholder 是否还在视口下方，未进入视口则 `teleport to="body"` 固定；`MutationObserver` 监听 DOM 变化重算相对 `offsetTarget` 的左偏移。 |
| **router-back** | 统一「返回」入口，优先执行 `useRouterBack` 注册的回调，否则 `history.back`；配合 `meta.routerBackName`。 |
| **scroll-faker** ★ | 自定义滚动条容器（横向 + 纵向、触底事件），是 `#auditNavigationContent` 的滚动体；emit `scroll` / `reach-bottom`；expose `scrollTo`。 |
| **statement-sidebar** | 报表中心侧边导航（`platfrom` / `reports` / `scene-config` / `system-manage` 四份），内含 `scene-system-selector` + `audit-menu`。 |

## 权限类

| 组件 | 形态与实现要点 |
| --- | --- |
| **auth/button** ★ | 按钮鉴权包装，额外支持 `resourceIsScene`（自动取当前场景 `scope_id`）。 |
| **auth/component** ★ | `.tsx` 通用包裹组件，可包裹任意内容。 |
| **auth/switch** ★ · **auth/option** ★ · **auth/router-link** ★ | 开关、下拉项、路由链接的鉴权形态。 |
| **auth/use-base.ts** | 共享核心逻辑：调 `IamManageService.check({action_ids, resources})`；`isShowRaw` 为真渲染原组件，否则渲染「原组件 + 半透明遮罩」，点击遮罩触发 `permissionDialog` 申请权限。 |
| **apply-permission** ★ | 无权限呈现：`page.vue` 整页、`catch.vue` 局部区块（全局注册名 `ApplyPermissionCatch`）、`dialog.vue` 弹窗、`render-result.vue` 结果渲染。由事件总线 `permission-page` / `permission-catch` 驱动。 |

## 选择器类

| 组件 | 职责与实现要点 |
| --- | --- |
| **audit-user-selector** | `bk-select` + `MetaManageService.fetchUserList` 远程模糊搜索（`fuzzy_lookups`，page_size 30）；`needRecord` 开启后把选过的人存 `sessionStorage['audit-userlist']`（最多 6 条）作为「最近使用」；`allowCreate` 允许输入不存在的用户名。 |
| **audit-user-selector-tenant** ★ | 租户版，改用 `@blueking/user-selector`，支持 `userGroup`（用户组）与 `freePaste`（粘贴离职人员也可保留）。 |
| **ip-selector** | CMDB 主机/拓扑选择器。无值时显示「添加目标」按钮（未选业务则禁用），有值显示「N 个动态节点/台主机」并支持重开；弹层体在 `selector-box/`（拓扑树 / 主机实例 / 服务与集群模板四种 `type`）；`isShow` 通过 `inject` 注入便于外层控制。 |
| **scene-system-selector** | 全局「审计场景 / 接入系统」切换器，写 localStorage 并同步 URL 上下文。props：`modelValue` / `systemPermission` / `scenePermission` / `listScope` / `dark`；emit `change`。 |

## 展示与反馈类

| 组件 | 职责与实现要点 |
| --- | --- |
| **audit-icon** ★ | 基于 `@lib/bk-icon` 雪碧图 / SVG symbol（`audit-icon-${type}`）。`type` 必须等于 `lib/bk-icon/iconcool.json` 里的 `icons[].name`（当前约 150 个）。props：`type`（必填）、`svg`。 |
| **skeleton-loading** ★ | 按 `name` 映射的骨架屏，内置 20+ 场景（如 `analysisList`）；props `name` / `loading` / `once` / `fullscreen`，配合 `use-skeleton` 在路由切换时启用。 |
| **show-tooltips-text** | 文本省略自动 hover 提示（单行 / 多行），基于 tippy。 |
| **version-log** | 版本日志弹窗：左侧版本列表 + 右侧 markdown 详情。打开时 `fetchVersions`，命中 `show_version` 自动弹窗；选中后 `fetchVersionContent` 取 markdown 渲染。 |
| **multiple-line-clamp** | 多行截断文本，溢出时自动出现「复制全部」。 |
| **render-sensitivity-level** ★ | 敏感等级色块（1 灰 / 2 绿 / 3 橙 / 4 红）。 |
| **relation-ship** ★ | 用双圆交叠可视化 SQL Join 类型（inner / left / right / full outer）。 |
| **audit-popconfirm** ★ | 基于 tippy 的二次确认气泡，支持异步确认/取消；props `title` / `content` / `confirmHandler` / `placement`；expose `hide()`。 |
| **audit-collapse-panel** ★ | 轻量折叠面板，标题可自定义；插槽 `label` 暴露 `handleClick` 与 `isCollapseActive`。 |
| **audit-sideslider** ★ | 侧滑弹层模板：内置确定/取消、离开确认，通过 `useModelProvider` 自动查找子组件 `submit` 方法。 |

---

> [← 文档索引](./README.md) ｜ 上一篇：[核心业务流程](./business-flows.md) ｜ 下一篇：[Hooks 与工具函数](./hooks-and-utils.md)
