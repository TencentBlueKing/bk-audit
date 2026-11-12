# 开发约定

> [← 文档索引](./README.md) ｜ 上一篇：[领域层](./domain-layer.md)

## 路由 meta 约定

| 字段 | 作用 |
| --- | --- |
| `navName` | 所属顶部导航组：`auditRiskManage` / `auditStatement` / `toolsSquare` / `auditConfigurationManage` / `sceneConfiguration` / `nweSystemManage` / `platformManage` |
| `keepAlive` | 是否缓存（由 `keep-alive-router-view` 读取） |
| `keepAliveKey` | 缓存 key，支持同一路由多实例（如 `toolsSquarePage`） |
| `permission` | 动作 ID，守卫中用 `IamManageService.checkAny` 校验，失败跳 `handleManage` |
| `sideMenus` | 侧边菜单配置数组 |
| `activeRoute` | 菜单高亮指向的实际路由名（解决跨模块引用） |
| `isNoBack` | 隐藏返回按钮 |
| `routerBackName` | 配合 `router-back` 组件与 `use-router-back` |
| `nodeSideContent` | 自定义侧边内容插槽（如 `permissionsPage`） |
| `isShowSceneSelector` | 是否显示全局场景选择器 |

## 列表页标准骨架

```
<audit-router-view>              <!-- 权限兜底 + keepAlive 缓存 -->
└─ index.vue
   ├─ <scene-system-selector>    <!-- 需要场景维度时（meta.isShowSceneSelector） -->
   ├─ <search-box>               <!-- 筛选条件 → URL，expose exportData() -->
   ├─ <tdesign-list>             <!-- 新增列表优先：TDesign，支持跨页全选 -->
   │  或 <render-list>           <!-- 存量 bk-table 页继续复用，不要无故回退或裸铺表格 -->
   ├─ <smart-action>             <!-- 底部操作栏自动吸底 -->
   └─ <audit-form>               <!-- 表单：校验失败自动滚动 + 脏值拦截 -->
```

配套约定：

- 新增列表优先 `<tdesign-list>`；存量 `<render-list>` 页继续改该封装，不要无故回退 `bk-table`，也不要在业务页裸铺 `PrimaryTable` / `bk-table`
- 数据：`@service/xxx` → `@model/xxx`；请求：`useRequest(service.fetchXxx)`
- 权限按钮：`<auth-button action-id="xxx" />`
- 提示：`use-message`（`messageSuccess` / `messageWarn` / `messageError`）
- 分页记忆：`use-record-page`；列设置：`use-table-settings`
- 需要缓存：在 router meta 打 `keepAlive: true`

## 主题

细节见 [全局主题](./theme.md)。

- 页面级白卡片挂 `bk-theme-card`；卡片里的表格不写外框（场景级联自动去掉）
- 圆角、阴影走场景 token / 场景类，业务页不直接写 `var(--bk-theme-radius-*)` / `var(--bk-theme-shadow-*)`
- 颜色用语义 token；页面内局部间距只写 `var(--bk-theme-space-N)`，不用 `.mt8` 等已冻结原子类
- 表单、Dialog、Sideslider 的间距跟场景，变体用 `bk-theme-form--compact` / `--inline`，不在页面覆盖
- bkui / TDesign 的公共外观改 `src/css/theme/`，不要在单个业务页覆盖表头色、行 hover 和控件圆角
- 新增或调整场景按 `bk-audit-theme` 的 `scene-workflow.md`
- 改完执行 `node scripts/check-theme-tokens.mjs`（业务页违规只减不增）

## 常用服务速查

| 场景 | Service |
| --- | --- |
| 风险列表 / 详情 / 处置 / 导出 | `RiskManageService` |
| 策略 / 联表 / 控制版本 | `StrategyManageService` · `LinkDataManageService` · `ControlManageService` |
| 处理规则 / 处理套餐 | `RuleManageService` · `ProcessApplicationManageService` |
| 系统 / 采集 / dataid / 存储 | `MetaManageService` · `CollectorManageService` · `DataidManageService` · `StorageManageService` |
| 鉴权 / 角色 / 启动配置 | `IamManageService`（`check` / `checkAny` / `getApplyData`）· `RootManageService`（`config` / `getUserPermission`） |
| 场景 / 通知组 / 报表 / 工具 | `SceneManageService` · `NoticeGroup` · `StatementManageService` · `ToolManageService` |
| 检索 / 事件 / ITSM / SOPS | `EsQuery` · `EventManageService` · `ItsmManageService` · `SoapManageService` |

## 常用命令

```bash
npm run dev           # Vite 开发服务器，默认 https://localhost:8082
                      # 可用 AUDIT_DEV_DOMAIN 指定自定义域名（自动配置 host + allowedHosts）
npm run build         # run-s type-check build-only
npm run build-only    # vite build --mode release（NODE_OPTIONS=--max-old-space-size=4096）
npm run type-check    # vue-tsc --noEmit
npm run preview       # vite preview --port 4173
npm run lint-script   # eslint --fix
npm run lint-style    # stylelint --fix
npm run build-server  # esbuild 打包 server/index.js
npm run server        # 运行打包后的静态服务
```

## 工程规范

| 项 | 说明 |
| --- | --- |
| 环境变量 | 前缀统一为 `AUDIT_`（`envPrefix`），如 `AUDIT_VITE_BUILD_BASE_DIR`、`AUDIT_DEV_DOMAIN` |
| 提交规范 | Commitlint（conventional）+ Husky；提交前 lint-staged 自动对 `src/**` 执行 eslint 与 stylelint 修复 |
| 导入排序 | `eslint-plugin-simple-import-sort` 强制 |
| 组件自动导入 | `unplugin-vue-components`（仅 `src/components` 目录，`dts: true`） |
| Node 版本 | `>= 16.16.0`（`.nvmrc`） |
| 构建分包 | `vue` / `@vue` / `vue-router` / `vue-i18n` 打入 `vue-vendor` chunk |

---

> [← 文档索引](./README.md) ｜ 上一篇：[领域层](./domain-layer.md)
