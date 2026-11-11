# Miffy 16 类组件覆盖矩阵

冻结时间：2026-11-09。实施目录为风险白名单 worktree。命名切换前的 token 与公共场景类快照在 `.ui-workflow/theme-freeze/`。

落地标记：

- 全局映射：库变量或 `theme/bkui.css` / `theme/tdesign.css` 公共选择器
- 公共封装：审计自己的 Vue 封装消费场景类
- 逐页迁移：业务页私有覆盖，按模块批次删除
- 规格缺口：miffy 未确认、或审计稿私有值，不推断成全局规范

| 组件 | 已冻结的 miffy 值 | 当前落点 | 标记 | 状态覆盖 | 缺口 |
| --- | --- | --- | --- | --- | --- |
| Table | 有框圆角 8；线 Neutral/8；表头底 Neutral/9；斑马白 / Neutral/10；表头字 Text/3、正文 Text/2 | `table-frame` 圆角 8；bkui 表格变量与 `.bk-table` 选择器；TDesign 表头/行高 | 全局映射 + 逐页迁移 | normal、hover、selected 有选择器；斑马纹用 surface-subtle | 表头底仍是 ext `#FAFBFD`，不是已证实的 Neutral/9。hover `#EEF2F8` 未证实为 miffy 全库值。无框变体圆角 2 没有单独场景 |
| Alert | 圆角 6；info/warn/danger/success 背景 Brand/6、Warn/6、Danger/6、Success/6；无可见描边 | `alert` 场景。`.bk-alert` 圆角 6，类型底用 fill-info/success/warn/danger，描边透明 | 全局映射 | info、success、warning、danger/error | 成功色旧值未测，只采用 miffy 新值。Message 仍是 8px |
| Editable | 外框圆角 8；线 Neutral/7；标题底 Neutral/9；禁用底 Neutral/10；hover 线 Brand/4 | `editable-table` 场景。TDesign 只覆盖 `td .t-input` 的边线、hover/focus、禁用底 | 全局映射 | 单元格编辑 normal、hover、focus、disabled | 没有可编辑表根节点，外框圆角不单独拆，避免误伤普通表。标题底 token 已登记，未绑到无类名的表头 |
| Button | 圆角 6；主色 Brand/2；hover Brand/3；高度 26/32/40 | `--border-radius-base` 与按钮 hover/active/disabled 变量 | 全局映射 | normal、hover、active、disabled | 库原高度与非 8 倍数间距保留，不改成 8 倍数 |
| Tag | 方角圆角 4；胶囊大号仍 11；浅蓝底 Brand/6；描边 Brand/4 | `.bk-tag` 用 `!important` 统一成 tag 圆角 4。原因：bkui 把圆角写在内联 style | 全局映射 | 方角 normal 被统一；胶囊被误伤 | 胶囊 8/9/11 不能收成一个值。浅蓝 hover 旧值未采，miffy 值为 Brand/5。P13 不能再把 4 和 999 写成二选一 |
| Form | 垂直布局 label 与控件 gap 6；容器圆角 0；控件圆角跟 Input 6 | `form-label-gap` 绑到 `.bk-form--vertical` 与 `.bk-form-item--vertical` 的 label | 全局映射 + 公共封装 | 垂直 label、compact、inline | 不把所有表单改成垂直布局 |
| Input | 非下划线圆角 6；禁用底 Neutral/10；禁用线 Neutral/7 | `control` 圆角 6；`--input-disabled-bg/border` | 全局映射 | normal、disabled；error 依赖库 | 下划线变体圆角 0，不能被 6 覆盖 |
| Select | 选择框圆角 6；下拉圆角 12；线框禁用 Neutral/10 + Neutral/7；填充已选禁用 Neutral/9 | 控件圆角与 overlay 圆角；禁用底走 Input 的 Neutral/10 | 全局映射 | normal、disabled 只覆盖线框 | 填充已选禁用底 Neutral/9 未单独映射 |
| Input-search | 线框/填充圆角 6；下划线 0；线框白底 + Neutral/6；填充 Neutral/8 | 线框走 `.bk-input`。填充由页面挂 `.bk-theme-search-filled`，不批量改存量 | 全局映射 + 场景类 | 线框、下划线；填充待页面挂类 | 库没有填充类 |
| SearchSelect | 圆角 6；常规线 Neutral/6；激活 Brand/2；hover 线 Neutral/5；填充底 Neutral/8，hover Neutral/7 | 线框走 `.bk-search-select-container`。填充由页面在 `bk-search-select` 上挂 `.bk-theme-search-filled` | 全局映射 + 场景类 | normal、hover、focus；填充待页面挂类 | 库没有填充类，存量页面未批量挂 |
| Dialog | 圆角 16；底 Neutral/11 | `dialog` 圆角与阴影 | 全局映射 | normal | 脚部间距未逐层对照，不推断。P20 继续沿用 bkui 默认内边距 |
| Sideslider | 根圆角保持 0；标题线 Neutral/7；脚部底 Neutral/10；脚部样本 pad 8/24 | 标题线 Neutral/7，固定脚部底 Neutral/10，左右 padding 仍沿用 bkui | 全局映射 + 公共封装 | 标题线、固定脚部 | 根圆角不改成 16。脚部高度和垂直 padding 未逐层采样，不改。默认确认/取消按钮已去掉内联宽度 |
| Tab | 下划线底线 Neutral/6、根圆角 0；色块大 8、色块小 6、数字胶囊全圆角 | 下划线头圆角 0。card-grid 用 8，card-tab 用 6，椭圆数字用全圆角 | 全局映射 | 下划线、色块大、色块小、数字胶囊 | 方角数字徽标仍是库内 2px |
| Tooltip | 内容容器圆角 6；根圆角 0；黑底 80% 未改 | `.bk-popper.dark/.light` 圆角 6。Popover 仍走 overlay 12 | 全局映射 | dark、light 内容容器 | 不新增 80% 黑的 alpha token |
| Collapse | 圆角 6；底 Neutral/8；高度 32/24 保留 | `.bk-collapse-block` 头圆角 6、底 Neutral/8；禁用文字用 text-disabled | 全局映射 | block normal、disabled | 库默认头高 46，miffy 的 32/24 未改。不把业务折叠卡写进库主题 |
| Navigation | 浅色侧栏线 Neutral/7；菜单字号 14/22；圆角 8 只在有绑定的菜单项 | 自定义 `audit-navigation` + nav token。不换成 `bk-navigation` | 公共封装 | 顶栏、侧栏选中 | 菜单色 P15：库文案 #6E7993，现值为 ext #6B7996，保持待确认 |

三级策略：库有 CSS 变量则在 `:root` 映射；没有变量就在主题文件写稳定公共选择器并覆盖状态；只有内联 style 才允许主题层最小范围 `!important`，原因和库版本写在选择器旁。
