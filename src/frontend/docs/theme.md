# 全局主题

> [← 文档索引](./README.md)

颜色、圆角、字号、间距、阴影与视觉场景的唯一真相源是 `src/css/tokens.css` 里的 `--bk-theme-*`。组件库外观只在 `src/css/theme/` 覆盖，场景组合类在 `theme/scenes.css`。不要在业务页再写一套同名变量，也不要保留旧的 `--bk-theme-brand-01` / `--bk-theme-neutral-*` / `--bk-theme-radius-control` 别名。

## 加载顺序

`src/main.ts` 使用静态导入，顺序固定：

1. 第三方：bkui、图标、通知、日期、TDesign 表格与分页、`@blueking/tdesign-ui` 的补充样式
2. `tokens.css` → `reset.css` → `common.css`
3. `theme/index.css`（`bkui.css` → `tdesign.css` → `scenes.css`）

覆盖层必须最后加载。不要在页面或列表组件里再单独引入 TDesign CSS。

## 四层 token

| 层 | 前缀 | 用途 |
| --- | --- | --- |
| 原始色 | `--bk-theme-color-brand/neutral/success/warn/danger-N`、`--bk-theme-color-ext-*` | 对齐 miffy Design Mode；`ext` 放设计稿要求单独命名的审计特例色（页面底、表格 hover、表头底、侧栏选中底、搜索描边、分类色…），只有这里写 hex |
| 语义 | `--bk-theme-text-*`、`--bk-theme-surface-*`、`--bk-theme-border-*`、`--bk-theme-fill-*`、`--bk-theme-status-*`、`--bk-theme-nav-*`、`--bk-theme-table-*`（颜色）、`--bk-theme-category-*` | 颜色按语义引用。通用选中底用 `--bk-theme-fill-selected`，不借 `--bk-theme-nav-side-active-bg` |
| 尺度 | `--bk-theme-radius-*`、`--bk-theme-space-*`、字体、`--bk-theme-shadow-*` | 只表示档位。圆角和阴影只给场景层用；业务页局部间距写 `var(--bk-theme-space-N)` |
| 场景 | 每组上方有 `@scene` 注册注释：`card`、`table-frame`、`control`、`tag`、`tab`、`alert`、`tooltip`、`collapse`、`editable-table`、`overlay`、`dialog`、`sideslider`、`form` 等 | 绑定在可复用组件或固定结构上的视觉组合。改一个场景只改一行 |

场景清单（含每个 token 的当前值和待确认项）由 `bk-audit-theme` 的 `build_profile.py` 生成到 skill 的 `references/profile/scenes.md`，这里不重复列值。

## 场景类

`src/css/theme/scenes.css`，只引用场景 token：

| 类 | 用途 |
| --- | --- |
| `.bk-theme-card` | 页面级白卡片。卡片内的表格自动 0 圆角、无外框（改写 `--bk-theme-table-frame-*`） |
| `.bk-theme-card--flush` / `--hoverable` / `--lg` / `--stack`、`.bk-theme-card__footer` | 无内边距 / hover 阴影 / 16 圆角大卡片 / 纵向区块 gap / 底栏 |
| `.bk-theme-form--compact` / `.bk-theme-form--inline` | 表单项间距紧凑 / 表格内或行内表单 |
| `.bk-theme-search-card`、`.bk-theme-select-banner`、`.bk-theme-cell-tip`、`.bk-theme-list-toolbar` | 智能搜索卡片、已选提示条、单元格 tips 虚线、列表工具栏 |
| `.bk-theme-search-filled` | 填充搜索。挂在 `bk-input` 或 `bk-search-select` 上。线框不加，不和 `behavior="simplicity"` 同时用 |
| `.bk-theme-search-filled` | 填充搜索。挂在 `bk-input` 或 `bk-search-select` 上。线框不加，不和 `behavior="simplicity"` 同时用 |
| `.bk-theme-search-filled` | 填充搜索。挂在 `bk-input` 或 `bk-search-select` 上。线框不加，不和 `behavior="simplicity"` 同时用 |

## 写法规则（每类只有一种写法）

| 要写的东西 | 写法 |
| --- | --- |
| 页面级白卡片 | 模板挂 `bk-theme-card`，不在本地写 radius / shadow / bg |
| 填充搜索框 | 组件上挂 `bk-theme-search-filled`。线框搜索不加 |
| 填充搜索框 | 组件上挂 `bk-theme-search-filled`。线框搜索不加 |
| 填充搜索框 | 组件上挂 `bk-theme-search-filled`。线框搜索不加 |
| 表单、Dialog、Sideslider 的间距 | 跟场景；变体用场景类，不覆盖 `.bk-form-item` margin 或 `.bk-dialog-*` / `.bk-sideslider-*` padding |
| 颜色 | 语义 token |
| 页面内局部间距 | `var(--bk-theme-space-N)` |

禁止：业务页直接写 `var(--bk-theme-radius-*)` / `var(--bk-theme-shadow-*)`；字面量 px 间距、圆角、阴影、hex、alpha；新代码用 `.mt8` 等 margin 原子类（`reset.css` 里已冻结，只保留存量）；新增 `space-40`。

## 谁改哪里

| 要改的外观 | 改这里 | 不要改 |
| --- | --- | --- |
| 某个场景的值（卡片圆角、表单间距…） | `tokens.css` 场景层那一行 | 业务页 |
| 新增场景 | 按 `bk-audit-theme/references/scene-workflow.md` | 在业务页自拟一套 |
| 按钮、输入、弹层、bk-table 等 bkui 默认外观 | `theme/bkui.css`（绑场景 token） | 单个页面的宽高和业务状态色 |
| PrimaryTable 表头、行高、hover、选中行、筛选弹层 | `theme/tdesign.css` | 把跨页全选、新增行高亮收成表格默认态 |
| 场景组合类 | `theme/scenes.css` | — |
| 基础元素 | `reset.css` | 新增原子类 |
| z-index、吸底、空表固定列等结构修复 | `common.css` | 把颜色再写回这里 |
| 顶栏、侧栏、页底、页面标题 | `audit-navigation` / `audit-menu` / `layout.vue`（引用 `shell-*`、`page` 场景） | 各业务页自己的标题结构 |

## 校验

在前端根执行：

```bash
node scripts/check-theme-tokens.mjs
python3 .agents/skills/bk-audit-theme/references/profile/build_profile.py --root "$PWD"
```

`check-theme-tokens.mjs` 检查：旧 token 已消失；引用都有定义；分层方向（语义层不写 hex、场景层不直接引用原始色阶）；`@scene` 注册表一致（有 token、类存在、废弃场景无人用）；业务页违规写法按文件计数，与 `scripts/theme-baseline.json` 比较只减不增。存量下降后用 `--update-baseline` 刷新，不能借此放宽。

页面验收用 `bk-audit-ui-verification` 的 `scene-audit.js`，期望值从场景 token 运行时读取。

## 页面迁移

剩余页面的迁移目标、顺序、旧值对照和进度见 [主题存量迁移](./theme-migration.md)。


- 改到旧文件时，本次 diff 碰到的写法按上面规则改；不要顺手重排业务布局。
- 页面级白卡片迁移：模板加 `bk-theme-card`（或 `bk-theme-card bk-theme-card--flush`），删掉本地 `background` / `border-radius` / `box-shadow` / `padding`。scoped 样式优先级高于场景类，不删会被覆盖。
