# 业务模块

> [← 文档索引](./README.md) ｜ 上一篇：[功能地图](./feature-map.md) ｜ 下一篇：[核心业务流程](./business-flows.md)

## 模块清单

| 目录 | 路由前缀 | 中文名 | 核心职责 | 关键能力 |
| --- | --- | --- | --- | --- |
| `analysis-manage` | `/analysis-manage` | 日志检索 | 审计日志多条件检索与可视化分析 | 场景/系统选择器、search-box 条件构造、结果表格、结果图表、字段统计、导出 |
| `attention-manege` | `/attention-manage` | 我的关注 | 关注的风险单列表 | 列表缓存、复用风险详情 |
| `event-manage` | `/event-manage` | 事件检索 | 原始审计事件查询与告警详情 | 搜索选择器、时间范围、alarm-detail 侧滑 |
| `handle-manage` | `/handle-manage` | 待我处理 | 待当前用户处理的风险工单 | 列表缓存、风险详情、处置入口（根路由默认首页） |
| `link-data-manage` | `/link-data-manage` | 联表管理 | 策略可用的联表（Join）数据模型 | 列表、新建/编辑字段映射、详情反查关联策略 |
| `new-system-manage` | `/nwe-system-manage/:id?` | 系统接入（新版） | 接入引导、系统信息、系统诊断 | 引导页、四步接入向导、完成页 |
| `notice-group` | `/notice-group` | 通知组 | 场景内通知组（人员/渠道）管理 | 列表、用户变量选择 |
| `platform-manage` | `/platform` | 平台管理 | 平台级全局配置 | 场景管理、全局报表、全局工具 |
| `process-application-manage` | `/application-manage` | 处理套餐 | 风险处置套餐（绑定 SOPS 模板） | 新建/编辑/克隆、执行动作、ITSM 审批配置 |
| `processed-manage` | `/processed-manage` | 处理历史 | 已处理风险归档查询 | 列表缓存、风险详情 |
| `risk-manage` | `/risk-manage` | 所有风险 | 风险单主模块 | 列表、自然语言搜索、AI 分析/报告、风险详情与处置面板、新增风险 |
| `rule-manage` | `/rule-manage` | 处理规则 | 风险自动分派/处理规则 | 适用范围条件组、关联处理套餐、批量优先级调整 |
| `scene-config` | `/scene-config` | 场景配置 | 单场景全套配置中心 | 场景信息、报表管理、工具管理、权限申请页 |
| `scene-risk-manage` | `/scene-risk-manage` | 场景风险 | 场景维度风险视图 | 列表缓存、风险详情、场景切换（唯一 `isShowSceneSelector`） |
| `statement-manage` | `/statement-manage` | 报表 | 报表/订阅详情展示 | 空态与权限申请、报表详情 |
| `storage-manage` | `/storage-manage` | 数据存储 | ES 存储集群/节点纳管 | 列表、新建/编辑、连通性检测、节点属性详情 |
| `strategy-manage` | `/strategy-manage` | 审计策略 | 策略（含 AIOPS）全生命周期 | 四步新建向导、编辑/克隆、升级详情、事件预览 |
| `system-manage` | `/system-manage` | 系统管理 | 接入系统的模型、数据上报与采集 | 系统列表、系统详情、日志上报、字段清洗、采集完成页 |
| `tool-manage-shared` | 无路由（共享层） | 工具建模共享 | 复用于场景级与平台级工具管理 | create-tool 向导、API/数据搜索/BKVision、工具状态 |
| `tools` | `/tools` | 工具广场 | 工具发现与执行 | 广场列表、工具详情、结果弹窗、审计画像 |

## 模块体量分布

| 模块 | 文件数 |
| --- | --- |
| strategy-manage | 89 |
| system-manage | 83 |
| risk-manage | 64 |
| platform-manage | 61 |
| analysis-manage | 57 |
| scene-config | 56 |
| tool-manage-shared | 39 |
| tools | 33 |
| new-system-manage / link-data-manage | 15 / 15 |
| storage-manage / event-manage / rule-manage / notice-group | 12 / 11 / 10 / 10 |
| 其余 5 个轻量视图模块 | 3 ~ 9 |

## 复杂度集中的模块

| 模块 | 说明 |
| --- | --- |
| **risk-manage** | 业务闭环核心，依赖 14 个 service（risk / strategy / rule / event / itsm / soap / tool 等），含自然语言搜索、AI 风险分析、处置面板与事件时间线 |
| **strategy-manage** | 配置侧最复杂的表单编排：四步向导 + AIOPS 方案 + 联表引用 + 控制版本升级 + 事件预览 |
| **system-manage** | 系统接入主干：接入模型、数据上报（API PUSH / DataID / 采集）、字段清洗、数据检查 |
| **analysis-manage** | 检索体验核心：search-box + 结果表格/图表 + 字段级联 + 导出，组件嵌套最深 |
| **scene-config / platform-manage + tool-manage-shared** | 三者共用工具建模实现，覆盖场景级与平台级两级权限 |
| **new-system-manage** | 新版接入流程，与 `system-manage` 并存且共享 `sideMenus` |

## 模块内部结构约定

每个业务模块目录的典型结构：

```
views/<module>/
├── routes.ts / routes/index.ts   # 路由定义（含 meta、子路由、sideMenus）
├── index.vue                     # 列表页或主页面
├── detail/                       # 详情页（如适用）
├── create/ 或 edit/              # 新建/编辑页（如适用）
├── components/                   # 模块内私有组件
├── config.ts / constants.ts      # 表格列配置、常量
└── hooks/ 或 utils/              # 模块内私有逻辑（如适用）
```

跨模块复用页面时使用 `@views` 别名直接引用，例如五个风险视图共用 `@views/risk-manage/detail/index.vue`。

---

> [← 文档索引](./README.md) ｜ 上一篇：[功能地图](./feature-map.md) ｜ 下一篇：[核心业务流程](./business-flows.md)
