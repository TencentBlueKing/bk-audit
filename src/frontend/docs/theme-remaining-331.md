# 主题存量缺口与组件规范落地核对

日期：2026-11-09。工作区：风险白名单 worktree。库版本：bkui-vue `2.0.2-beta.71`。

校验口径：`node scripts/check-theme-tokens.mjs` 当前基线 **331** 处。组件核对看的是 `src/css/tokens.css` 场景 token、`src/css/theme/bkui.css`、`src/css/theme/tdesign.css`，以及库里对应 CSS 是变量还是写死的类。

## 1. 这 331 处为什么没换

不全是「token 里没有这个色」。颜色只占 177 处。其余 154 处是间距、阴影、圆角，或者业务页盖掉了场景内边距。

| 原因 | 处数 | 说明 |
| --- | --- | --- |
| 色阶里没有同值的纯色 | 95 | 标签紫、代码区深色、字段类型色等。色阶有接近值，但不是同一个值，就近替换会改颜色 |
| 颜色带透明度 | 82 | 遮罩、滚动条、`#979ba54d` 这类。token 只有实色 |
| 阴影对不上 | 73 | 现有只有卡片、下拉、弹窗几档，对不上 `0 1px 2px`、`0 12px 32px` |
| 间距不在档位 | 48 | 档位是 2/4/6/8/12/16/24/32。这里是 `80px` 留白、`220px` 偏移等 |
| 圆角不是场景档 | 21 | 场景档是 4/6/8/12/16。这里是 `999px`、`9px`、光斑 `52.8px` |
| 覆盖了场景内边距 | 8 | 弹窗、侧栏 footer 写了 `padding: 0`，为了内容贴边 |
| 直接用了尺度 token | 4 | 工具广场卡片用了 `radius-8`、`radius-full`，没有对应场景 token |

逐条原值和位置见文末清单。指纹在 `scripts/theme-baseline.json`。

## 2. 16 类组件规范有没有盖到组件上

结论：已确认的 miffy 值，库有 CSS 变量的都在 `:root` 映射了；库把值写死、没有变量的，按库里的真实类名加了覆盖。没有全部套上的，是库里没有稳定类、或者规范明确不能收成一个值的项。

库版本写在选择器注释里。`!important` 只用在 Tag 圆角和人员选择器：库把圆角写进内联 style 或更高优先级的属性选择器。

| 组件 | 已套上的 | 库没有变量时怎么盖的 | 没有套上的 |
| --- | --- | --- | --- |
| Table | 外框圆角 8；表头字、行高、hover、选中行 | 库有 `--table-head-bg-color` 等，已映射。表头节点另有选择器，避免内部标题不吃变量 | 表头底仍是 ext `#FAFBFD`，不是已证实的 Neutral/9 `#EEF2F7`。hover 仍是 ext `#EEF2F8`。无框变体圆角 2 没有单独场景 |
| Alert | 圆角 6；info/success/warning/danger 底；描边透明 | 库把底色写死在 `.bk-alert-info/success/warning/danger`（如 `#f0f8ff`），没有 `--alert-*`。主题用同名类覆盖 | 成功色旧值未采，只用 miffy Success/6。Message 仍是 8 |
| Editable | 单元格边线 Neutral/7；hover/focus 线 Brand/4；禁用底 Neutral/10；标题底 Neutral/9 | TDesign 没有可编辑表根节点。只盖 `td .t-input`。标题底用 `:has(tbody td .t-input)`，普通表没有这个节点 | 外框圆角 8 与表格外框相同，不再单独写 |
| Button | 圆角 6；主色 hover Brand/3、active Brand/1 | 库有 `--border-radius-base`、`--button-primary-hover-color` 等，已映射 | 高度 26/32/40 保持库值，不改成 8 的倍数 |
| Tag | 方角圆角 4、高 22 | 库把圆角写进内联 style，没有变量。`.bk-tag { border-radius: tag-radius !important }` | 胶囊 11 被同一条 `!important` 收成 4。库没有胶囊类，拆不开。浅蓝 hover Brand/5 未单独映射 |
| Form | 垂直 label 与控件间距 6；compact / inline 变体 | 库把垂直 label 的 `margin-bottom: 6px` 写死。覆盖 `.bk-form--vertical .bk-form-label` 和 `.bk-form-item--vertical .bk-form-label` | 不把所有表单改成垂直。容器圆角仍是 0 |
| Input | 圆角 6；禁用底 Neutral/10、禁用线 Neutral/7；下划线变体圆角 0 | 库有 `--input-disabled-bg`。内层 `.bk-input--text` 把白底和 `border-radius: 2px` 写死，所以外框加了 `overflow: hidden`，内层圆角改为 0 | 填充搜索见 `.bk-theme-search-filled`，不批量挂 |
| Select | 选择框圆角 6；下拉外壳圆角 12；线框禁用跟 Input | 库用更长的选择器把 `.bk-popover.bk-pop2-content.bk-select-popover` 锁在 2px。主题用同一条链盖外壳，并把内部 `.bk-select-dropdown` 圆角收成 0 | 线框禁用底已收到 Neutral/9。下划线不铺这块底 |
| Input-search | 线框圆角跟控件 6 | 线框是 `.bk-input`。填充由页面挂 `.bk-theme-search-filled` | 存量页面未批量挂 |
| SearchSelect | 圆角 6；常规线 Neutral/6；hover Neutral/5；focus Brand/2 | 库有 `--search-select-focus-border-color`，已映射。填充由页面在组件上挂 `.bk-theme-search-filled` | 存量页面未批量挂 |
| Dialog | 外壳圆角 16、阴影 | 库把圆角写在 `.bk-modal-body`（2px），不是 `.bk-modal-content`。主题盖 body / infobox / notify，正文圆角收成 0，全屏再收成 0 | 脚部间距未逐层对照，继续用库默认 |
| Sideslider | 标题线 Neutral/7；固定脚部底 Neutral/10；根圆角保持 0 | 库把头部分割线和脚部底写死。覆盖 `.bk-sideslider-header` 的 border，以及 `.bk-modal-footer.is-fixed .bk-sideslider-footer` 的背景 | 根圆角不改成 16。脚部高度和垂直 padding 未采样，不改 |
| Tab | 下划线底线 Neutral/6、根圆角 0；色块大圆角 8、色块小 6；数字胶囊全圆角 | 下划线头圆角 0。card-grid 头和内容区用 tab 圆角 8，card-tab 用 6。数字椭圆胶囊用全圆角，选择器跟库内 18px 那条链一样长 | 方角数字徽标仍是库内 2px，miffy 没有单独写成 4 或 6 |
| Tooltip | 内容容器圆角 6 | `v-bk-tooltips` 的节点是 `.bk-popper.dark/.light`，不是 `.bk-popover`。只盖这个类的圆角 | 黑底 80% 不新增 alpha token，背景保持库值 |
| Collapse | 块头圆角 6、底 Neutral/8；禁用文字 | 库把 `.bk-collapse-block .bk-collapse-item .bk-collapse-header` 写成 `#F0F1F5` 和 `2px`，没有变量。用同一条选择器覆盖 | 库默认头高 46，miffy 的 32/24 未改 |
| Navigation | 顶栏、侧栏宽、选中底、边线走 nav token | 产品用的是 `audit-navigation`，不是 `bk-navigation`。token 在 `audit-navigation/index.vue` 里消费 | 菜单字色仍是 ext `#6B7996`，不是未确认的 `#6E7993` |

## 3. 库没有 token 时，覆盖是否按真实节点写

是。下面这些库里没有对应 CSS 变量，覆盖选择器取自 bkui `2.0.2-beta.71` / tdesign 的实际样式，不写在内层节点上。

| 库里的写法 | 真实节点 | 主题里的覆盖 |
| --- | --- | --- |
| Alert 类型底色写死 hex | `.bk-alert-info` 等 | 同名类改成 fill-info/success/warn/danger，描边透明 |
| 输入框内层写死 `border-radius: 2px` | `.bk-input--text`、`textarea` | 外框 `overflow: hidden`，内层圆角 0；`.is-simplicity` 保持 0 |
| 下拉外壳选择器更长，锁在 2px | `.bk-popover.bk-pop2-content.bk-select-popover`、`.bk-dropdown-menu` | 同一条链圆角 12；列表 `.bk-select-dropdown` 圆角 0 |
| 弹窗圆角在外壳 | `.bk-dialog .bk-modal-body` | 外壳圆角 16；`.bk-modal-content` 圆角 0 |
| 折叠块头写死 `#F0F1F5`、2px | `.bk-collapse-block .bk-collapse-item .bk-collapse-header` | 同选择器：底 Neutral/8，圆角 6 |
| Tag 圆角在内联 style | `.bk-tag` | 只把内联 `2px` 压成方角 4；胶囊仍用传入的半径 |
| 可编辑单元格 | `.t-table td .t-input` | 只改边线和禁用底，不给普通表加外框 |
| Tooltip 内容不是 Popover | `.bk-popper.dark`、`.bk-popper.light` | 只改圆角 6 |

线框 Select 的禁用底用 `.bk-select-tag.is-disabled:not(.is-simplicity)` 收到 Neutral/9。下划线 Select 不铺这块底。

填充搜索没有库类。场景类 `.bk-theme-search-filled` 由页面挂到 `bk-input` 或 `bk-search-select` 上，存量页面不批量挂。可编辑表标题只加在含 `tbody td .t-input` 的表上。

## 4. 331 处清单

同一原值只列前几个文件，处数是全部出现次数。

### 色阶里没有同值的纯色（95）

| 原值 | 处数 | 出现位置 |
| --- | --- | --- |
| `#000` | 7 | `components/version-log/index.vue`、`views/platform-manage/report-config/index.vue`、`views/platform-manage/report-config/index.vue` 等 7 处 |
| `#788779` | 4 | `views/rule-manage/list/components/risk-rule-detail.vue`、`views/strategy-manage/list/components/aiops/filter-condition.vue`、`views/strategy-manage/list/components/aiops/index.vue` 等 4 处 |
| `#ba69f4` | 3 | `components/scene-system-selector/index.vue`、`components/scene-system-selector/index.vue`、`components/statement-sidebar/reports.vue` |
| `#1cc2fe` | 3 | `views/risk-manage/list/components/ai-analyzes-tip/dialog.vue`、`views/sec-chat/audit-log-retrieval/components/log-analyze-dialog.vue`、`views/sec-chat/audit-log-retrieval/components/log-statistics-dialog.vue` |
| `#a469ff` | 3 | `views/risk-manage/list/components/ai-analyzes-tip/dialog.vue`、`views/sec-chat/audit-log-retrieval/components/log-analyze-dialog.vue`、`views/sec-chat/audit-log-retrieval/components/log-statistics-dialog.vue` |
| `#6366f1` | 3 | `views/system-manage/log-create/components/bkbase/pages/step1/index.vue`、`views/system-manage/log-create/components/newlog/collector/pages/step1/index.vue`、`views/system-manage/log-create/components/newlog/collector/pages/step2/index.vue` |
| `#7bbe8a` | 2 | `views/analysis-manage/list/components/search-box/components/search-cascader/index.vue`、`views/analysis-manage/list/components/search-result-table/components/setting-field/components/setting-field.vue` |
| `#d4f3e1` | 2 | `views/platform-manage/report-config/components/report-group-list.vue`、`views/scene-config/report-config/components/report-group-list.vue` |
| `#e8fbf0` | 2 | `views/platform-manage/report-config/components/report-group-list.vue`、`views/scene-config/report-config/components/report-group-list.vue` |
| `#45e06f` | 2 | `views/platform-manage/scene-manage/components/inline-user-field.vue`、`views/scene-config/scene-info/components/base-info.vue` |
| `#ff5656` | 2 | `views/platform-manage/scene-manage/components/inline-user-field.vue`、`views/scene-config/scene-info/components/base-info.vue` |
| `#fafdff` | 2 | `views/risk-manage/list/components/ai-analyzes-tip/dialog.vue`、`views/sec-chat/audit-log-retrieval/components/log-analyze-dialog.vue` |
| `#488bff` | 2 | `views/risk-manage/list/components/nl-search-box/components/nl-input.vue` 等 2 处 |
| `#ebecf3` | 2 | `views/sec-chat/audit-log-retrieval/components/retrieval-card-skeleton.vue`、`views/sec-chat/audit-log-retrieval/components/retrieval-guide-card.vue` |
| `#e4e9f2` | 2 | `views/strategy-manage/list/components/render-label.vue` 等 2 处 |
| `#ffc107` | 2 | `views/strategy-manage/strategy-create/components/step1/components/customize/components/expected-results/add-fields.vue`、`views/strategy-manage/strategy-create/components/step1/components/customize/components/expected-results/add-fields.vue` |
| `#242424` | 2 | `views/system-manage/detail/components/data-report/components/render-operation/delivery-info/components/deploy-log.vue`、`views/system-manage/log-create/components/newlog/collector/pages/step3/components/deploy-log.vue` |
| `#fbfbfc` | 2 | `views/tool-manage-shared/create-tool/components/data-search/components/edit-sql.vue`、`views/tool-manage-shared/create-tool/components/data-search/sql-model/index.vue` |
| `#fff0f0` | 2 | `views/tools/tools-square/components/audit-profile/profile-user-info.vue`、`views/tools/tools-square/components/audit-profile/profile-user-info.vue` |
| `#a3a6ad` | 2 | `views/tools/tools-square/components/dialog/api-search-result.vue`、`views/tools/tools-square/components/dialog/data-search-result.vue` |
| `#242d3f` | 1 | `components/scene-system-selector/index.vue` |
| `#4d5565` | 1 | `components/scene-system-selector/index.vue` |
| `#5a5f71` | 1 | `components/scene-system-selector/index.vue` |
| `#f6f6f6` | 1 | `components/version-log/index.vue` |
| `#e1e1e8` | 1 | `components/version-log/index.vue` |
| `#dfdfdf` | 1 | `components/version-log/index.vue` |
| `#34383e` | 1 | `components/version-log/index.vue` |
| `#d14` | 1 | `components/version-log/index.vue` |
| `#979797` | 1 | `views/404.vue` |
| `#e1edff` | 1 | `views/new-system-manage/landing-page/index.vue` |
| `#e6f1ff` | 1 | `views/new-system-manage/landing-page/index.vue` |
| `#ff6ec7` | 1 | `views/new-system-manage/landing-page/index.vue` |
| `#a3a7b1` | 1 | `views/platform-manage/scene-manage/components/table-select-picker.vue` |
| `#c43bff` | 1 | `views/risk-manage/list/components/nl-search-box/components/nl-input.vue` |
| `#5392ff` | 1 | `views/risk-manage/list/components/nl-search-box/index.vue` |
| `#9e8bff` | 1 | `views/risk-manage/list/components/nl-search-box/index.vue` |
| `#db82fe` | 1 | `views/risk-manage/list/components/nl-search-box/index.vue` |
| `#eae8ff` | 1 | `views/risk-manage/list/components/nl-search-box/index.vue` |
| `#fff3e1` | 1 | `views/scene-config/scene-info/components/scene-table.vue` |
| `#d3dbe8` | 1 | `views/strategy-manage/list/components/render-label.vue` |
| `#30bc9e` | 1 | `views/strategy-manage/list/components/risk-detection.vue` |
| `#326746` | 1 | `views/strategy-manage/list/components/rule-condition-display.vue` |
| `#235dfa` | 1 | `views/strategy-manage/strategy-create/components/event-report/ai-editor/ai-model.vue` |
| `#eb8cec` | 1 | `views/strategy-manage/strategy-create/components/event-report/ai-editor/ai-model.vue` |
| `#dde4eb` | 1 | `views/strategy-manage/strategy-create/components/event-report/ai-editor/ai-model.vue` |
| `#f2f3f6` | 1 | `views/strategy-manage/strategy-create/components/step-risk-rules/index.vue` |
| `#fff3cd` | 1 | `views/strategy-manage/strategy-create/components/step1/components/customize/components/expected-results/add-fields.vue` |
| `#856404` | 1 | `views/strategy-manage/strategy-create/components/step1/components/customize/components/expected-results/add-fields.vue` |
| `#29bc9e` | 1 | `views/strategy-manage/strategy-create/components/step1/components/customize/components/expected-results/index.vue` |
| `#0eac8c` | 1 | `views/strategy-manage/strategy-create/components/step1/components/customize/components/expected-results/index.vue` |
| `#212121` | 1 | `views/system-manage/log-create/components/newlog/collector/pages/step2/components/container/problems.vue` |
| `#b34747` | 1 | `views/system-manage/log-create/components/newlog/collector/pages/step2/components/container/problems.vue` |
| `#2e2e2e` | 1 | `views/system-manage/log-create/components/newlog/collector/pages/step2/components/container/yaml.vue` |
| `#ebfaf0` | 1 | `views/tool-manage-shared/create-tool/components/bkvision/index.vue` |
| `#0f0503` | 1 | `views/tool-manage-shared/create-tool/components/data-search/components/edit-sql-tip.vue` |
| `#f5f5f5` | 1 | `views/tool-manage-shared/create-tool/components/data-search/components/edit-sql-tip.vue` |
| `#7f879b` | 1 | `views/tool-manage-shared/create-tool/components/data-search/components/edit-sql-tip.vue` |
| `#a1e3ba` | 1 | `views/tool-manage-shared/create-tool/components/data-search/components/edit-sql-tip.vue` |
| `#3858ff` | 1 | `views/tool-manage-shared/create-tool/components/data-search/components/field-reference/index.vue` |
| `#e1efff` | 1 | `views/tools/tools-square/components/audit-profile/profile-user-info.vue` |
| `#fff8ed` | 1 | `views/tools/tools-square/components/audit-profile/profile-user-info.vue` |
| `#d4e4ff` | 1 | `views/tools/tools-square/components/game/game-detail.vue` |
| `#5897ff` | 1 | `views/tools/tools-square/index.vue` |
| `#e1e2e6` | 1 | `views/tools/tools-square/square-content/concent-card.vue` |

### 带透明度的颜色（82）

| 原值 | 处数 | 出现位置 |
| --- | --- | --- |
| `rgb(0 0 0 / 4%)` | 8 | `views/platform-manage/report-config/components/report-create-sideslider.vue`、`views/scene-config/report-config/components/report-create-sideslider.vue`、`views/sec-chat/audit-log-retrieval/components/chat-log-panel.vue` 等 8 处 |
| `rgba(255, 255, 255, 0.45)` | 6 | `views/process-application-manage/list/components/execution-detail.vue`、`views/process-application-manage/list/components/execution-detail.vue`、`views/process-application-manage/list/components/execution-records.vue` 等 6 处 |
| `rgb(20 165 104 / 30%)` | 5 | `views/attention-manege/index.vue`、`views/handle-manage/index.vue`、`views/processed-manage/index.vue` 等 5 处 |
| `rgb(0 0 0 / 6%)` | 4 | `components/ip-selector/selector-box/components/preview-result/collapse-box/content-item.vue`、`components/smart-action/index.vue`、`views/sec-chat/audit-log-retrieval/components/retrieval-guide-card.vue` 等 4 处 |
| `rgb(255 255 255 / 35%)` | 4 | `components/show-tooltips-text/index.vue`、`components/show-tooltips-text/index.vue`、`views/sec-chat/styles/scrollbars.css` 等 4 处 |
| `rgb(0 0 0 / 40%)` | 3 | `components/editor-image-preview/index.vue`、`views/sec-chat/audit-log-retrieval/components/log-analyze-dialog.vue`、`views/sec-chat/audit-log-retrieval/components/log-statistics-dialog.vue` |
| `rgb(0 0 0 / 80%)` | 3 | `components/editor-image-preview/index.vue`、`components/editor-image-preview/index.vue`、`components/editor-image-preview/index.vue` |
| `rgb(255 255 255 / 45%)` | 3 | `components/scene-system-selector/index.vue`、`components/scene-system-selector/index.vue`、`components/scene-system-selector/index.vue` |
| `rgb(255 255 255 / 90%)` | 2 | `components/editor-image-preview/index.vue`、`components/editor/index.vue` |
| `rgb(255 255 255 / 55%)` | 2 | `components/show-tooltips-text/index.vue`、`views/sec-chat/styles/scrollbars.css` |
| `rgb(0 0 0 / 15%)` | 2 | `components/version-log/index.vue`、`views/tools/tools-square/components/audit-profile/profile-user-info.vue` |
| `rgb(59 126 255 / 14%)` | 2 | `views/new-system-manage/landing-page/index.vue`、`views/new-system-manage/landing-page/index.vue` |
| `rgba(234, 54, 54, 0.6)` | 2 | `views/process-application-manage/list/components/execution-detail.vue`、`views/process-application-manage/list/components/execution-records.vue` |
| `rgba(44, 175, 94, 0.6)` | 2 | `views/process-application-manage/list/components/execution-detail.vue`、`views/process-application-manage/list/components/execution-records.vue` |
| `rgb(246 247 251 / 80%)` | 2 | `views/sec-chat/audit-log-retrieval/components/retrieval-card-skeleton.vue`、`views/sec-chat/audit-log-retrieval/components/retrieval-guide-card.vue` |
| `rgb(255 255 255 / 22%)` | 2 | `views/statement-manage/detail/index.vue`、`views/statement-manage/detail/index.vue` |
| `rgb(255 86 245 / 8%)` | 2 | `views/strategy-manage/strategy-create/components/event-report/ai-editor/ai-model.vue`、`views/strategy-manage/strategy-create/components/event-report/ai-editor/ai-model.vue` |
| `rgb(255 221 221 / 20%)` | 2 | `views/system-manage/log-create/components/field-cleaning/components/select-map-value.vue`、`views/tool-manage-shared/create-tool/components/data-search/components/field-reference/select-map-value.vue` |
| `#979ba54d` | 1 | `components/audit-user-selector-tenant/index.vue` |
| `rgb(0 0 0 / 20%)` | 1 | `components/editor-image-preview/index.vue` |
| `rgb(0 0 0 / 28%)` | 1 | `components/editor-image-preview/index.vue` |
| `rgb(0 0 0 / 60%)` | 1 | `components/editor-image-preview/index.vue` |
| `rgb(0 0 0 / 30%)` | 1 | `components/editor-image-preview/index.vue` |
| `rgb(105 157 244 / 25%)` | 1 | `components/scene-system-selector/index.vue` |
| `rgb(186 105 244 / 25%)` | 1 | `components/scene-system-selector/index.vue` |
| `rgb(248 182 79 / 25%)` | 1 | `components/scene-system-selector/index.vue` |
| `rgba(58, 132, 255, .2)` | 1 | `components/scene-system-selector/index.vue` |
| `rgb(0 0 0 / 50%)` | 1 | `components/scene-system-selector/index.vue` |
| `rgb(151 155 165 / 80%)` | 1 | `components/scroll-faker/index.vue` |
| `rgb(151 155 165 / 90%)` | 1 | `components/scroll-faker/index.vue` |
| `rgb(255 255 255 / 20%)` | 1 | `components/scroll-faker/index.vue` |
| `rgb(255 255 255 / 28%)` | 1 | `components/scroll-faker/index.vue` |
| `rgb(255 232 195 / 20%)` | 1 | `views/analysis-manage/list/components/search-result-table/components/row-diff-detail/components/diff-detail.vue` |
| `rgb(0 0 0 / 5%)` | 1 | `views/analysis-manage/list/index.vue` |
| `rgb(59 126 255 / 6%)` | 1 | `views/new-system-manage/landing-page/index.vue` |
| `#0000000a` | 1 | `views/new-system-manage/system-access/steps/index.vue` |
| `#1919290d` | 1 | `views/new-system-manage/system-access/steps/step1/index.vue` |
| `#3a84ff1f` | 1 | `views/platform-manage/scene-manage/components/table-select-picker.vue` |
| `rgb(255 255 255 / 60%)` | 1 | `views/risk-manage/list/components/ai-analyzes-tip/dialog.vue` |
| `rgb(25 25 41 / 5%)` | 1 | `views/rule-manage/list/components/batch-priority-index-slider.vue` |
| `rgb(245 247 250 / 100%)` | 1 | `views/rule-manage/list/components/risk-rule-detail.vue` |
| `rgb(255 255 255 / 38%)` | 1 | `views/statement-manage/detail/index.vue` |
| `rgb(151 155 165 / 30%)` | 1 | `views/strategy-manage/list/index.vue` |
| `rgb(250 251 253 / 40%)` | 1 | `views/strategy-manage/strategy-create/components/event-report/ai-editor/index.vue` |

### 阴影对不上（73）

| 原值 | 处数 | 出现位置 |
| --- | --- | --- |
| `0 12px 32px 0 rgb(0 0 0 / 4%)` | 6 | `views/sec-chat/audit-log-retrieval/components/chat-log-panel.vue`、`views/sec-chat/audit-log-retrieval/components/condition-filter-card.vue`、`views/sec-chat/audit-log-retrieval/components/retrieval-card-skeleton.vue` 等 6 处 |
| `0 1px 2px 0 #00000029` | 4 | `views/platform-manage/report-config/components/report-create-sideslider.vue`、`views/scene-config/report-config/components/bkvision-param-config.vue`、`views/scene-config/report-config/components/report-create-sideslider.vue` 等 4 处 |
| `0 1px 2px 0 rgb(0 0 0 / 16%)` | 4 | `views/system-manage/log-create/components/field-cleaning/components/card.vue`、`views/system-manage/log-create/components/field-cleaning/components/field-map/alternative-field.vue`、`views/system-manage/log-create/components/newlog/collector/pages/step3/index.vue` 等 4 处 |
| `0 1px 2px 0 rgb(0 0 0 / 8%)` | 3 | `views/analysis-manage/list/components/search-result-table/components/row-expand-content/components/log-box/index.vue`、`views/system-manage/detail/components/data-report/components/render-operation/delivery-info/index.vue`、`views/system-manage/log-create/components/newlog/collector/pages/step3/index.vue` |
| `0 2px 16px rgb(59 126 255 / 8%)` | 3 | `views/scene-config/landing-page/index.vue`、`views/scene-config/landing-page/user-landing.vue`、`views/scene-config/permissions-page/index.vue` |
| `0 2px 6px 0 rgb(0 0 0 / 10%)` | 3 | `views/system-manage/list/components/system-access-dropdown.vue`、`views/system-manage/list/components/system-access-dropdown.vue`、`views/tools/tools-square/components/game/record-detail-table.vue` |
| `0 4px 20px rgb(59 126 255 / 14%)` | 2 | `views/new-system-manage/landing-page/index.vue`、`views/new-system-manage/landing-page/index.vue` |
| `0 -1px 3px 0 rgb(0 0 0 / 4%)` | 2 | `views/platform-manage/report-config/components/report-create-sideslider.vue`、`views/scene-config/report-config/components/report-create-sideslider.vue` |
| `0 2px 8px rgb(0 0 0 / 15%)` | 2 | `views/platform-manage/report-config/components/report-group-list.vue`、`views/scene-config/report-config/components/report-group-list.vue` |
| `0 4px 12px rgb(0 0 0 / 15%)` | 2 | `views/platform-manage/report-config/components/report-group-list.vue`、`views/scene-config/report-config/components/report-group-list.vue` |
| `0 2px 6px rgb(0 0 0 / 20%)` | 2 | `views/platform-manage/report-config/index.vue`、`views/platform-manage/tool-manage/index.vue` |
| `0 10px 24px rgb(0 0 0 / 10%)` | 2 | `views/sec-chat/components/chat-sidebar.css`、`views/sec-chat/components/chat-sidebar.css` |
| `0 1px 2px rgb(0 0 0 / 8%)` | 2 | `views/strategy-manage/strategy-create/components/event-report/ai-editor/ai-model.vue`、`views/strategy-manage/strategy-create/components/event-report/ai-editor/ai-model.vue` |
| `inset 0 1px 0 0 #0000001f` | 2 | `views/tool-manage-shared/create-tool/components/data-search/components/simple-model/raw-name-batch.vue`、`views/tool-manage-shared/create-tool/components/data-search/components/simple-model/raw-name-select.vue` |
| `0 0 3px 0 var(--bk-theme-color-brand-4)` | 1 | `components/application-parameter/index.vue` |
| `0 2px 4px rgb(58 132 255 / 20%)` | 1 | `components/editor-image-preview/index.vue` |
| `0 4px 20px rgb(0 0 0 / 30%)` | 1 | `components/editor-image-preview/index.vue` |
| `0 0 16px 0 rgb(0 0 0 / 12%)` | 1 | `components/editor/index.vue` |
| `0 1px 2px 0 rgb(0 0 0 / 6%)` | 1 | `components/ip-selector/selector-box/components/preview-result/collapse-box/content-item.vue` |
| `0 3px 9px 0 rgb(0 0 0 / 50%)` | 1 | `components/scene-system-selector/index.vue` |
| `0 -2px 4px 0 rgb(0 0 0 / 6%)` | 1 | `components/smart-action/index.vue` |
| `0 2px 4px 0 rgb(0 0 0 / 5%)` | 1 | `views/analysis-manage/list/index.vue` |
| `0 1px 8px rgb(59 126 255 / 6%)` | 1 | `views/new-system-manage/landing-page/index.vue` |
| `0 2px 20px rgb(59 126 255 / 10%)` | 1 | `views/new-system-manage/landing-page/index.vue` |
| `0 4px 24px rgb(59 126 255 / 12%)` | 1 | `views/new-system-manage/landing-page/index.vue` |
| `0 3px 4px 0 #0000000a` | 1 | `views/new-system-manage/system-access/steps/index.vue` |
| `0 2px 4px 0 #0000001a, 0 2px 4px 0 #1919290d` | 1 | `views/new-system-manage/system-access/steps/step1/index.vue` |
| `0 4px 16px 0 rgb(25 25 41 / 10%)` | 1 | `views/platform-manage/tool-manage/create-tool/components/visible-range-field.vue` |
| `0 0 0 3px color-mix(in srgb, var(--dot-color) 24%, transparent)` | 1 | `views/risk-whitelist/components/status-flow-popover.vue` |
| `0 2px 4px 0 rgb(0 0 0 / 10%), 0 2px 4px 0 rgb(25 25 41 / 5%)` | 1 | `views/rule-manage/list/components/batch-priority-index-slider.vue` |
| `0 4px 16px rgb(0 0 0 / 12%)` | 1 | `views/sec-chat/audit-log-retrieval/components/json-field-preview.vue` |
| `0 1px 2px rgb(0 0 0 / 6%)` | 1 | `views/sec-chat/audit-log-retrieval/components/retrieval-guide-card.vue` |
| `0 2px 10px rgb(0 0 0 / 12%)` | 1 | `views/sec-chat/components/chat-input.vue` |
| `0 2px 12px rgb(58 132 255 / 12%)` | 1 | `views/sec-chat/components/chat-input.vue` |
| `0 2px 8px rgb(0 0 0 / 6%)` | 1 | `views/sec-chat/components/chat-input.vue` |
| `0 2px 10px 0 rgb(0 0 0 / 12%)` | 1 | `views/sec-chat/components/chat-sidebar.css` |
| `0 2px 4px 0 rgb(0 0 0 / 15%)` | 1 | `views/sec-chat/components/chat-sidebar.css` |
| `0 2px 6px 0 rgb(0 0 0 / 20%)` | 1 | `views/sec-chat/components/chat-sidebar.css` |
| `-6px 0 0 0 var(--bk-theme-table-header-bg)` | 1 | `views/strategy-manage/list/index.vue` |
| `0 2px 6px #0000001a` | 1 | `views/strategy-manage/strategy-create/components/step1/components/customize/components/expected-results/add-fields.vue` |
| `inset 0 1px #0000001f` | 1 | `views/strategy-manage/strategy-create/components/step1/components/customize/components/expected-results/add-fields.vue` |
| `0 2px 4px 0 rgb(0 0 0 / 16%)` | 1 | `views/system-manage/log-create/components/newlog/collector/pages/step2/components/container/yaml.vue` |
| `0 2px 4px 0 rgb(0 0 0 / 12%)` | 1 | `views/system-manage/log-create/components/newlog/collector/pages/step2/components/wild-card.vue` |
| `0 -4px 10px -2px rgb(0 0 0 / 8%), 3px 0 8px -3px rgb(0 0 0 / 8%)` | 1 | `views/tools/tools-square/components/game/game-detail.vue` |
| `-3px 0 6px 0 rgb(0 0 0 / 10%)` | 1 | `views/tools/tools-square/index.vue` |
| `0 0 10px 0 rgb(0 0 0 / 10%)` | 1 | `views/tools/tools-square/index.vue` |
| `0 4px 8px 0 rgb(0 0 0 / 10%), 0 6px 12px 0 rgb(25 25 41 / 10%)` | 1 | `views/tools/tools-square/square-content/concent-card.vue` |
| `0 2px 12px 0 rgb(0 0 0 / 15%)` | 1 | `views/tools/tools-square/square-content/tool-info-panel.vue` |

### 间距不在档位（48）

| 原值 | 处数 | 出现位置 |
| --- | --- | --- |
| `80px` | 7 | `views/risk-manage/list/components/ai-analyzes-tip/dialog.vue`、`views/risk-whitelist/list/index.vue`、`views/scene-config/landing-page/index.vue` 等 7 处 |
| `1px` | 5 | `views/attention-manege/index.vue`、`views/handle-manage/index.vue`、`views/processed-manage/index.vue` 等 5 处 |
| `150px` | 2 | `views/404.vue`、`views/new-system-manage/system-access/steps/step1/index.vue` |
| `72px` | 2 | `views/new-system-manage/system-access/steps/step1/index.vue`、`views/sec-chat/audit-log-retrieval/components/log-analyze-dialog.vue` |
| `220px` | 2 | `views/system-manage/detail/components/access-model/components/action-list/add-action/index.vue`、`views/system-manage/detail/components/access-model/components/resource-type-list/components/add-resource/index.vue` |
| `0 var(--bk-theme-space-16) 0 26px` | 2 | `views/tools/tools-square/index.vue`、`views/tools/tools-square/index.vue` |
| `1.5px` | 1 | `components/application-parameter/index.vue` |
| `60px 20px 120px` | 1 | `components/editor-image-preview/index.vue` |
| `-33px -var(--bk-theme-space-24) -26px` | 1 | `components/version-log/index.vue` |
| `200px` | 1 | `components/version-log/index.vue` |
| `9.5px` | 1 | `components/version-log/index.vue` |
| `17px` | 1 | `views/analysis-manage/list/components/search-result-chart/components/commons/card.vue` |
| `11px` | 1 | `views/analysis-manage/list/components/search-result-table/components/render-field/components/desc-popover.vue` |
| `90px` | 1 | `views/new-system-manage/landing-page/index.vue` |
| `0 0 38px` | 1 | `views/new-system-manage/landing-page/index.vue` |
| `144px` | 1 | `views/new-system-manage/system-access/steps/step4/index.vue` |
| `192px` | 1 | `views/new-system-manage/system-access/steps/step4/index.vue` |
| `238px` | 1 | `views/new-system-manage/system-access/steps/step4/index.vue` |
| `-80px` | 1 | `views/risk-manage/detail/components/link-event.vue` |
| `36px 36px` | 1 | `views/scene-config/landing-page/index.vue` |
| `var(--bk-theme-space-4) 88px` | 1 | `views/sec-chat/audit-log-retrieval/components/log-statistics-dialog.vue` |
| `7px` | 1 | `views/sec-chat/components/chat-sidebar.css` |
| `7px var(--bk-theme-space-8) 7px 22px` | 1 | `views/sec-chat/components/chat-sidebar.css` |
| `var(--bk-theme-space-8) var(--bk-theme-space-12) var(--bk-theme-space-8) 36px` | 1 | `views/strategy-manage/strategy-create/components/event-report/preview-report.vue` |
| `74px` | 1 | `views/strategy-manage/strategy-create/components/step-basic-info/loading.vue` |
| `240px` | 1 | `views/strategy-manage/strategy-create/components/step1/components/control-description.vue` |
| `3px 108px 3px` | 1 | `views/strategy-manage/strategy-create/components/step1/components/customize/components/other-table-detail/index.vue` |
| `-20px -8px var(--bk-theme-space-8) -24px` | 1 | `views/strategy-manage/strategy-create/index.vue` |
| `110px` | 1 | `views/strategy-manage/strategy-create/upgrade/components/step1/index.vue` |
| `148px` | 1 | `views/system-manage/collector-complete/index.vue` |
| `0 5.2px` | 1 | `views/system-manage/detail/components/system-diagnosis/index.vue` |
| `var(--bk-theme-space-2) 26px` | 1 | `views/system-manage/log-create/components/data-inspection/index.vue` |
| `33px` | 1 | `views/system-manage/log-create/components/newlog/collector/pages/step3/index.vue` |
| `var(--bk-theme-space-16) clamp(var(--bk-theme-space-32), 6vw, 116px` | 1 | `views/tools/tools-square/components/game/game-detail.vue` |

### 圆角不是场景档（21）

| 原值 | 处数 | 出现位置 |
| --- | --- | --- |
| `9px` | 3 | `views/platform-manage/report-config/components/report-group-list.vue`、`views/scene-config/report-config/components/report-group-list.vue`、`views/system-manage/list/components/system-access-dropdown.vue` |
| `999px` | 3 | `views/tools/tools-square/square-content/add-tool-popover.vue`、`views/tools/tools-square/square-content/add-tool-popover.vue`、`views/tools/tools-square/square-content/tool-info-panel.vue` |
| `0 4px 4px` | 2 | `views/link-data-manage/list/components/render-label.vue`、`views/strategy-manage/list/components/render-label.vue` |
| `99px` | 2 | `views/sec-chat/audit-log-retrieval/components/log-statistics-dialog.vue`、`views/sec-chat/components/chat-sidebar.css` |
| `2px` | 1 | `components/ip-selector/selector-box/index.vue` |
| `7px` | 1 | `components/scroll-faker/index.vue` |
| `9999px` | 1 | `components/skeleton/skeleton.css` |
| `52.8px` | 1 | `views/risk-manage/list/components/nl-search-box/index.vue` |
| `72.8px` | 1 | `views/risk-manage/list/components/nl-search-box/index.vue` |
| `16px 0px 16px 16px` | 1 | `views/sec-chat/audit-log-retrieval/components/chat-log-panel.vue` |
| `14px` | 1 | `views/sec-chat/components/chat-input.vue` |
| `20px` | 1 | `views/sec-chat/components/chat-sidebar.css` |
| `24px` | 1 | `views/system-manage/log-create/components/data-inspection/index.vue` |
| `50% } .desc { font-size: 12px` | 1 | `views/tool-manage-shared/create-tool/components/data-search/components/edit-sql-tip.vue` |
| `16px 16px 8px 8px` | 1 | `views/tools/tools-square/components/dialog/dialog.vue` |

### 覆盖了场景内边距（8）

| 原值 | 处数 | 出现位置 |
| --- | --- | --- |
| `.bk-dialog-footer { padding` | 3 | `views/platform-manage/report-config/components/edit-visibility-dialog.vue`、`views/platform-manage/tool-manage/components/edit-visibility-dialog.vue`、`views/tool-manage-shared/components/delete-confirm-dialog.vue` |
| `.bk-dialog-content { height: 100%; padding` | 2 | `views/platform-manage/report-config/components/edit-visibility-dialog.vue`、`views/platform-manage/tool-manage/components/edit-visibility-dialog.vue` |
| `.bk-dialog-content { margin-top: var(--bk-theme-space-16); padding` | 1 | `views/process-application-manage/list/components/execution-retry-dialog.vue` |
| `.bk-sideslider-footer { display: flex; align-items: center; justify-content: flex-start...` | 1 | `views/sec-chat/audit-log-retrieval/components/log-report-drawer.vue` |
| `.bk-dialog-header { padding` | 1 | `views/tools/tools-square/components/dialog/dialog.vue` |

### 直接用了尺度 token（4）

| 原值 | 处数 | 出现位置 |
| --- | --- | --- |
| `var(--bk-theme-radius-8)` | 2 | `views/tools/tools-square/square-content/concent-card.vue`、`views/tools/tools-square/square-content/concent-card.vue` |
| `var(--bk-theme-radius-full)` | 2 | `views/tools/tools-square/square-content/concent-card.vue`、`views/tools/tools-square/square-content/concent-card.vue` |
