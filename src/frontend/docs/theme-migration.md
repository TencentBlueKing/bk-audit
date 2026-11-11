# 主题存量迁移

> [← 文档索引](./README.md) ｜ 规则见 [全局主题](./theme.md) 和 `bk-audit-theme` skill

本文只管「剩下的页面怎么迁、按什么顺序、迁到哪算完」。**怎么判断场景、该用哪个 token 的规则不在这里重复**，以 skill 为准：

| 要查什么 | 打开 |
| --- | --- |
| 每类东西只有一种写法（场景类 / 场景 token / 语义 token / `space-N`） | `.agents/skills/bk-audit-theme/SKILL.md`「怎么写样式」 |
| 一个值该不该做成场景、怎么新增 / 改值 / 废弃场景 | `.agents/skills/bk-audit-theme/references/scene-workflow.md` |
| 当前有哪些场景、每个 token 的值、待确认项 Pn | `.agents/skills/bk-audit-theme/references/profile/scenes.md`（生成物） |
| 色阶 / 文字语义对照 | `.agents/skills/bk-audit-theme/references/token-map.md` |
| 页面验收怎么跑 | `.agents/skills/bk-audit-ui-verification/references/visual.md` + `scripts/scene-audit.js` |

## 目标

业务页（`src/views`、`src/components`）不再出现：

| 规则 id（校验脚本里的名字） | 含义 | 迁成什么 |
| --- | --- | --- |
| `literal-radius` | 字面量圆角 `border-radius: 2px` 等 | 场景类，或 `var(--bk-theme-<场景>-radius)` |
| `literal-shadow` | 字面量阴影 | 场景类，或 `var(--bk-theme-card-shadow)` / `overlay-shadow` 等 |
| `literal-color` | hex / rgb / rgba | 语义 token（`--bk-theme-text-*` 等），语义对不上才用色阶 |
| `literal-spacing` | 字面量 px 的 padding / margin / gap | `var(--bk-theme-space-N)`；属于组件级场景的删掉本地值 |
| `scale-radius-shadow` | 直接写 `var(--bk-theme-radius-*)` / `var(--bk-theme-shadow-*)` | 场景 token 或场景类 |
| `frozen-utility` | 模板里的 `.mt8` / `.mb16` 等 | 样式里写 `var(--bk-theme-space-N)`，删掉类 |
| `scene-override` | 覆盖 `.bk-form-item` margin、`.bk-dialog-*` / `.bk-sideslider-*` padding | 删掉；要变体用 `bk-theme-form--compact` / `--inline`，或改写场景变量 |
| `space-40` | `var(--bk-theme-space-40)` | 换成规范档位（P18 裁决前可保留存量） |
| `annotation-color` | `#E5E5E5` 标注色 | 删除 |

终态：`scripts/theme-baseline.json` 的 `hits` 与 `modules` 都为空，且主要页面 `scene-audit.js` 无「值不符」「未接入场景类」。含 Pn 注释的规格结论是「待确认」，不能写成「符合」。

## 进度怎么看

在前端根执行：

```bash
# 按模块输出当前存量（markdown 表格），贴到下面「进度」表更新
node scripts/check-theme-tokens.mjs --report
# 日常校验：存量只减不增
node scripts/check-theme-tokens.mjs
```

每迁完一批，跑 `--update-baseline` 把下降后的数写回基线。基线是 version 2，且 `context` 为 `selector`：指纹为「文件 + 规则 + 属性 + 规范化值 + 选择器链」。上下文不含相邻声明。新指纹或模块合计上升时，脚本会拒绝刷新。`box-shadow: var()` 和 `box-shadow: none` 不计。

不计入指纹的只有四类：自定义属性定义、`1px` 边框 / outline 宽度、尺度层阴影里的合法 alpha（8% / 10% / 12% / 16% / 20%）、表格容器内控件自己的 `border-radius`。`--report` 另按模块、文件、规则、原值和场景识别器覆盖输出。

## 起点（2026-11-06）

共 57 个模块、472 个文件、7660 处。按规则分：

| 规则 | 处 |
| --- | --- |
| literal-color | 3817 |
| literal-spacing | 2736 |
| literal-radius | 472 |
| frozen-utility | 293 |
| literal-shadow | 202 |
| scale-radius-shadow | 91 |
| scene-override | 39 |
| space-40 | 10 |
| annotation-color | 1 |

已完成（不在上表）：全局主题层（`tokens.css`、`theme/*`）、壳层（`audit-navigation`、`audit-menu`、`layout.vue`、`app.vue`）、列表封装外框（`tdesign-list`、`render-list`）、场景信息页（基础信息、关联系统、关联数据表、KPI 卡）、处理套餐列表外层卡片、策略创建 / 工具创建 / 搜索区等 9 处卡片。

## 迁移顺序

先做「影响视觉一致性、且一处改动覆盖多页」的，再做纯数值替换。

### 第 1 批：视觉上明显不一致的场景（优先）

用户能一眼看出来的问题，先修：

1. **白卡片未接入**：页面级白底容器还写着 `border-radius: 2px` + `#fff`，共约 67 个文件。迁移：模板加 `bk-theme-card`（自控内边距加 `bk-theme-card--flush`），删掉本地 `background` / `border-radius` / `box-shadow` / `padding`。卡片里的表格会自动去外框，不要再写表格外框样式。
2. **`scene-override`**：28 个文件在业务页覆盖表单项间距或弹窗 / 侧滑内边距。逐个判断：
   - 只是把 `.bk-form-item` 的 `margin-bottom` 改成 0（表格内、行内表单）→ 表单挂 `bk-theme-form--inline`，删本地覆盖。
   - 改成 12 / 16 → 挂 `bk-theme-form--compact`；值不是 12 的，先记录，可能需要新场景（见下文「判断要不要新场景」）。
   - Dialog / Sideslider padding 覆盖 → 先量现状，若是这一类弹窗的通用做法，回到 P20 裁决默认值，否则保留并在文件里写原因。
3. **`scale-radius-shadow`**：91 处直接用 `radius-*` / `shadow-*`，大多在 `strategy-manage`、`sec-chat`。按视觉判断属于哪个场景后换成场景 token；是白卡片的直接改 `bk-theme-card`。

### 第 2 批：按模块整体迁移

一次迁一个模块，模块内一次性把该模块所有规则清零，便于验收和回滚。建议顺序（违规多、用户访问多的在前）：

| 顺序 | 模块 | 起点违规 | 说明 |
| --- | --- | --- | --- |
| 1 | `views/risk-manage` | 1002 | 风险列表 / 详情，访问量最高 |
| 2 | `views/strategy-manage` | 1335 | 策略列表 / 创建，含 43 处尺度 token |
| 3 | `views/tool-manage-shared` + `views/tools` | 743 + 496 | 工具创建 / 广场；ToolCard V2-A 单独立项，本批只做 token |
| 4 | `views/system-manage` + `views/new-system-manage` | 782 + 229 | 系统接入 |
| 5 | `views/sec-chat` | 741 | 含 31 处尺度 token、6 处 space-40 |
| 6 | `views/platform-manage` | 576 | 平台管理 |
| 7 | `views/scene-config`（剩余）+ `views/analysis-manage` | 441 + 202 | |
| 8 | 公共组件 `components/*` | 684 | `ip-selector`、`scene-system-selector`、`editor` 等；改公共组件影响多页，需页面回归 |
| 9 | 其余小模块 | — | `rule-manage`、`link-data-manage`、`notice-group` 等 |

### 第 3 批：收尾

- 冻结原子类清零后，删除 `reset.css` 里的 `.mt8` 等定义。
- P18 裁决后处理 `space-40`。
- `--bk-theme-table-radius` 兼容别名无人使用后删除。

## 单个文件怎么迁

按顺序做，每一步都对照 skill，不在这里另立规则：

1. **先看图再看代码**：在页面上截图，圈出这个文件渲染出的卡片 / 表格 / 弹层 / 表单。
2. **归场景**：每个视觉区块对照 `scenes.md`：
   - 是页面级白卡片 → `bk-theme-card`。
   - 是表格 → 用 `tdesign-list` / `render-list`，不写外框。
   - 是表单 / Dialog / Sideslider → 删本地间距覆盖，需要变体用场景类。
   - 是搜索卡片、已选提示条、单元格 tips、列表工具栏 → 对应场景类。
3. **颜色换语义**：按下面「旧值对照」换成语义 token。
4. **间距换档位**：px 换 `var(--bk-theme-space-N)`；不在 2/4/6/8/12/16/24/32 档位的值（如 10、14、20），取最近档位前先在页面确认视觉可接受，不能接受的记下来，不要新增尺度档。
5. **删冻结原子类**：模板里的 `mt8` 等改成样式里的 `var(--bk-theme-space-N)`。
6. **校验**：`node scripts/check-theme-tokens.mjs` 通过；该文件的计数下降；`--update-baseline`。
7. **验收**：BrowserOS 跑 `scene-audit.js`，该页面无「值不符」「未接入场景类」；和迁移前截图对比，布局无错位。

## 旧值对照（迁移时的查表）

存量最多的旧硬编码值，以及迁移到的目标。旧值来自旧主题（Magicbox 旧色板），和新规范不完全等值，**迁移后颜色会按新规范轻微变化，这是预期**。

| 旧值 | 出现次数 | 常见用途 | 迁成 |
| --- | --- | --- | --- |
| `#3a84ff` | 457 | 主色、链接、选中字 | `--bk-theme-color-brand-2` |
| `#fff` | 396 | 白底 | 卡片用 `bk-theme-card`；其他 `--bk-theme-surface-default` |
| `#dcdee5` | 391 | 边框、分割线 | `--bk-theme-border-default` |
| `#979ba5` | 380 | 次要文字、图标 | `--bk-theme-text-weak` |
| `#63656e` | 361 | 正文 | `--bk-theme-text-default` |
| `#c4c6cc` | 323 | 控件边框、失效文字 | 控件边框 `--bk-theme-border-strong`；文字 `--bk-theme-text-disabled` |
| `#313238` | 276 | 标题、强调文字 | `--bk-theme-text-strong` |
| `#f5f7fa` / `#f5f6fa` | 202 | 页面底、浅灰底 | 页面底 `--bk-theme-surface-page`；区块浅底 `--bk-theme-surface-subtle` |
| `#f0f1f5` | 161 | 灰底、Tag 底 | `--bk-theme-surface-muted`（P11 字段统计进度底待确认） |
| `#ea3636` | 159 | 错误、危险 | `--bk-theme-color-danger-2` |
| `#4d4f56` | 122 | 次标题 | `--bk-theme-text-default` |
| `#fafbfd` | 115 | 表头底 | `--bk-theme-table-header-bg` |
| `#e1ecff` | 56 | 选中底 | 侧栏用 `--bk-theme-nav-side-active-bg`；其他 `--bk-theme-fill-selected` |
| `#ff9c01` | 45 | 警告 | `--bk-theme-color-warn-2` |
| `#eaebf0` | 36 | 浅分割线 | `--bk-theme-border-weak` |
| `#a3c5fd` | 32 | 浅蓝描边 | `--bk-theme-color-brand-4` |
| `#f0f5ff` | 26 | 已选提示条 | `bk-theme-select-banner` 或 `--bk-theme-select-banner-bg` |
| `#2dcb56` / `#2caf5e` | 35 | 成功 | `--bk-theme-color-success-2` |
| `#699df4` | 21 | hover 蓝 | `--bk-theme-color-brand-3` |
| `border-radius: 2px` | 297 | 卡片、控件、Tag | 按场景：卡片 `bk-theme-card`；控件 / Tag 删本地值（库主题已覆盖） |
| `border-radius: 4px` | 43 | 小卡片、Tag | 按场景判断，多为 `--bk-theme-tag-radius` |
| `box-shadow: 0 2px 4px ...#1919290d` | 20 | 旧卡片阴影 | `bk-theme-card` |
| `box-shadow: 0 0 3px #a3c5fd` | 14 | 控件 focus | 删掉，库主题已处理 focus |

状态色（成功 / 警告 / 危险 Tag 的字色和底色）用 `--bk-theme-status-*`，值待 P7 裁决。上表没有的值，按 `token-map.md` 找语义最近的 token；找不到语义的，不写 hex，记入下面「迁移中发现的缺口」。

## 判断要不要新场景

迁移时最常见的困惑是「这个值要不要新建场景」。完整流程见 `scene-workflow.md`，这里只给迁移中的速判：

| 迁移中遇到 | 处理 |
| --- | --- |
| 多个模块都有一样的视觉组合（例如多页都有「白底 + 8px 圆角 + 浅边框」的信息块） | 新场景候选。先记入「缺口」表，攒够 2 处以上同类再按 `scene-workflow.md` 新增 |
| 只有这一页这样 | 不建场景，用语义 token + `space-N` 写 |
| 和已有场景只差一点（例如卡片 padding 20 而场景是 16/24） | 按场景值迁，迁移前后截图对比；差异影响阅读的记入缺口，不新建尺度档 |
| 规范里只是用途建议（「8 = 控件间距」） | 不是场景，用 `space-N` |
| 需要新颜色 | 先在设计稿 / 规范确认，再加 `--bk-theme-color-ext-*` 和语义 token，不在业务页写 hex |

新增场景后必须跑 `build_profile.py --root "$PWD"`，并在 `审计-风格升级差异-前端.md` 末尾的「场景 → token 对照索引」加一行。

## 进度

每完成一批更新本表（数据来自 `--report`）。

| 日期 | 范围 | 违规总数 | 备注 |
| --- | --- | --- | --- |
| 2026-11-06 | 起点（场景层落地后） | 7660 | 场景信息、处理套餐、9 处卡片已迁 |
| 2026-11-09 | 指纹基线冻结 | 1006 | 冻结前按规则计数 1063。豁免 token 定义、1px 边框、合法阴影 alpha、表格内控件圆角后为 1006。187 个 `--bk-theme-*`，18 个场景，未定义 token 0，旧 token 0。HEAD `ca393b0dd`，工作区 468 个文件未提交。 |
| 2026-11-09 | 风险白名单分段圆角 | 1002 | 有效期分段和匹配范围左轨改场景圆角；分组右内边距 25px 收到 space-24。空态 80px 和状态点光晕仍在缺口表。 |
| 2026-11-09 | 风险列表智能搜索 | 866 | 输入框改为白底、1px `#488BFF` 描边、高 40。表格卡片内边距改为四周 24，提示条上下间距都是 16。 |
| 2026-11-09 | 标题条与左侧菜单 | 865 | 标题高 32、距顶栏 16。侧栏宽 240，菜单距顶 16、项间距 4、选中圆角 8。未选字和图标都是 `#6B7996`，选中字和图标 `#3A84FF`、底 `#E1ECFF`。`#B0BDD5` 只用于收起按钮。 |
| 2026-11-09 | 全站可归并存量 | 371 | 对照表里的颜色、档位内间距、`space-40`、控件 2px 圆角和 focus 光晕已收进 token。371 处仍是 alpha、装饰渐变、80px 留白、胶囊 999、以及弹窗 footer 的 `padding: 0` 覆盖，不在这一批硬折。 |
| 2026-11-09 | 近色阶颜色与发丝阴影 | 331 | 差一档的灰、蓝、红、成功底改语义 token。表头发丝阴影改成 1px 边框。空态 80px、装饰渐变、半透明和弹窗 `padding: 0` 仍留在缺口。 |
| 2026-11-09 | 公共封装入口 | 331 | AuditForm 增加 density（default / compact / inline）。折叠面板标题改用 collapse 场景。公共组件的 `audit-m*` 间距类已收回各自选择器；视图里收回了 17 处能唯一对上选择器的，其余仍留在各文件。 |
| 2026-11-10 | 间距类与组件缺口 | 331 | 视图里的 `audit-m*` 已去掉，间距改到元素自己的 style 或已有选择器。Tag 只把默认 2px 收成方角，胶囊保留传入半径。线框 Select 禁用底改为 Neutral/9。HTML 原生 `title` 提示改为 `v-bk-tooltips` 或 `show-tooltips-text`。 |
| 2026-11-10 | 日期圆角与白名单匹配范围格 | 331 | 日期输入框改用库同长度选择器，圆角回到控件 6。白名单列表和命中记录的匹配范围格退出 42px / 上下 0 内边距，改为随内容增高、四周 8。 |
| 2026-11-10 | 表格内容行上下间距 | 331 | 内容单元格上 8、下 8、左右 16，整体行高保持 42。bk-table 的行高行距从原来的 38px 里扣掉这 16px，避免被撑成 54。表头上下仍是 0。 |
| 2026-11-10 | 组件选择器缺口 | 331 | 按钮组外角、表头筛选浮层改用库同长度选择器。色块大 8、色块小 6、数字胶囊全圆角。可编辑表标题只在含单元格输入框的表上改 Neutral/9。填充搜索仍没有独立类。 |
| 2026-11-10 | 填充搜索场景类 | 331 | 新增 `.bk-theme-search-filled`，挂到 `bk-input` 或 `bk-search-select` 上才是浅灰底。存量搜索框不批量挂。 |
| 2026-11-10 | 填充搜索场景类 | 331 | 新增 `.bk-theme-search-filled`，挂到 `bk-input` 或 `bk-search-select` 上才是浅灰底。存量搜索框不批量挂。 |
| 2026-11-10 | 填充搜索场景类 | 331 | 新增 `.bk-theme-search-filled`，挂到 `bk-input` 或 `bk-search-select` 上才是浅灰底。存量搜索框不批量挂。 |

冻结时按规则：literal-color 533、literal-spacing 200、literal-shadow 192、literal-radius 61、space-40 10、scene-override 8、frozen-utility 1、annotation-color 1。模块前五：`views/risk-manage` 142、`views/strategy-manage` 138、`views/sec-chat` 124、`views/tool-manage-shared` 57、`views/system-manage` 53。完整按文件 / 原值表用 `--report` 重算，不把 280 行文件表抄进本文。

## 迁移中发现的缺口

迁移时遇到规则覆盖不了的情况记在这里，攒够同类再决定新增场景或回设计确认。

| 日期 | 文件 | 现象 | 候选处理 |
| --- | --- | --- | --- |
| 2026-11-09 | `src/views/risk-whitelist/list/index.vue` | 空态 `padding: 80px 0`，没有 space-80 | 不改成 space-32。需要设计确认空态留白 |
| 2026-11-09 | `src/views/risk-whitelist/components/status-flow-popover.vue` | 状态点 `box-shadow: 0 0 0 3px color-mix(... var(--dot-color) 24%)` | 颜色随状态变，不能换成固定阴影 token。要消掉字面阴影需单独的状态点场景 |
| 2026-11-09 | `nl-input.vue` | 加载文案渐变 `#488BFF` / `#C43BFF` | 输入框描边已改白底实线。这段渐变只留在加载文案上 |
| 2026-11-09 | `nl-search-box/index.vue` | 右上角光斑 `#5392FF` / `#EAE8FF` / `#9E8BFF` / `#DB82FE`，圆角 52.8 / 72.8 | 光斑色和椭圆半径不在色阶。卡片底、描边、外圆角改走 `.bk-theme-search-card` |
| 2026-11-09 | 全站剩余 371 处 | alpha、装饰渐变、`80px` 留白、滚动条 `999px`、弹窗 footer `padding: 0` | 不折进最近档。alpha 和渐变要设计确认后才能加 ext；`padding: 0` 是满铺弹窗，删掉会叠上场景内边距 |

## 验收要求

每批迁移完成时：

- `node scripts/check-theme-tokens.mjs` 退出码 0，基线已刷新且只降不升。
- 改了全局样式时，`build_profile.py --root "$PWD" --check` 为 up-to-date。
- 本批涉及的主要页面在 BrowserOS 跑 `scene-audit.js`：无「值不符」；「未接入场景类」只剩明确不纳入的区块（在缺口表里写原因）。
- 迁移前后截图对比，布局无错位、无换行变化；颜色按新规范的轻微变化是预期。
- `npm run type-check` 不新增错误。
