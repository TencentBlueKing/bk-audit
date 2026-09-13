# 核心业务流程

> [← 文档索引](./README.md) ｜ 上一篇：[业务模块](./business-modules.md) ｜ 下一篇：[公共组件](./components.md)

## 风险主链路

`risk-manage` / `handle-manage` / `processed-manage` / `attention-manege` / `scene-risk-manage` 是**同一风险实体的五个视图**：`detail/:riskId` 全部复用 `@views/risk-manage/detail/index.vue`，差异仅在列表页的 `dataSource`。

| 模块 | 数据源 | 语义 |
| --- | --- | --- |
| risk-manage | `fetchRiskList` | 全量风险（唯一带 `permission: list_risk_v2`） |
| handle-manage | `fetchTodoRiskList` | 当前处理人是我 |
| processed-manage | `fetchProcessedRiskList` | 我处理过的 |
| attention-manege | `fetchWatchRiskList` | 我关注的 |
| scene-risk-manage | `fetchRiskList` + 场景参数 | 场景维度收窄 |

### 状态机

```mermaid
flowchart TD
    S["strategy-manage 审计策略"] -->|命中输出| E["审计事件"]
    E --> R["风险单 new"]
    RL["rule-manage 处理规则<br/>scope 条件 + priority_index"] -->|匹配| R
    R -->|规则命中| AP["process-application-manage 处理套餐"]
    R -->|无规则| AD["await_deal 人工处理"]
    AP --> FA["for_approve ITSM 审批"] --> AUTO["auto_process SOPS 执行"]
    AUTO -->|成功且 auto_close_risk| C["closed"]
    AUTO -->|OperateFailed| AD
    AD --> PR["processing"] --> C
    C -->|"ReOpen（risk_label=normal）"| AD
    C --> EX["RiskExperience 风险总结"]
    R -.->|MisReport| MIS["risk_label=misreport"]
    MIS -.->|ReOpenMisReport| R
    R --> V["五视图列表"]
    V --> D["risk-manage/detail/index.vue 共用详情"]
```

- **主状态**（`views/risk-manage/constants.ts`）：`new` → `await_deal` → `processing` / `for_approve` / `auto_process` → `closed`
- **正交标记** `risk_label`：`normal` / `misreport`（误报）
- **时间轴动作**：`NewRisk` · `await_deal` · `MisReport` · `ReOpenMisReport` · `ForApprove` · `AutoProcess` · `CustomProcess` · `OperateFailed` · `CloseRisk` · `ReOpen` · `RiskExperience`

### 关键文件

| 文件 | 作用 |
| --- | --- |
| `views/risk-manage/detail/index.vue` | 五视图共用详情 |
| `views/risk-manage/detail/components/risk-handle/` | 处置面板：await-deal / for-approve / closerisk / custom-process / misreport / reopen-misreport / risk-experience |
| `views/risk-manage/constants.ts` | 状态与动作枚举 |
| `views/risk-manage/table-columns/risk/use-columns.ts` | 列表列定义 |
| `domain/model/risk/risk.ts` | 风险模型（含 `ticket_history`） |
| `domain/service/risk-manage.ts` | 风险相关接口 |

## 策略 / 规则 / 联表

| 概念 | 定位 | 关键字段 |
| --- | --- | --- |
| 审计策略 `strategy-manage` | 风险**发现端**：定义什么算风险，产出事件与风险单 | `config_type`（EventLog / LinkTable / 其他表）、`rules`、`expected_results`、`drill_config` |
| 处理规则 `rule-manage` | 风险**处置端**：消费风险，绑定处理套餐 | `scope`（适用条件组）、`pa_id`（套餐）、`pa_params`、`auto_close_risk`、`priority_index` |
| 联表 `link-data-manage` | 策略的数据源之一 | 被 step1 以 `configs.data_source.link_table = { uid, version }` 引用 |
| 处理套餐 `process-application-manage` | 处置执行单元 | `sops_template_id`、`need_approve` |

```mermaid
flowchart LR
    DS1["审计日志 EventLog"] --> ST1
    DS2["联表 LinkTable"] --> ST1
    DS3["其他表 / AIOPS 模型"] --> ST1
    ST1["Step1 风险发现"] --> ST2["Step2 单据展示<br/>字段映射 + 下钻工具"]
    ST2 --> ST3["Step3 事件调查报告<br/>AI 报告编辑器"]
    ST3 --> ST4["Step4 其他配置"] --> SUB["提交 → 询问是否启用"]
    SUB --> EV["策略命中 → 审计事件 → 风险单"]
    EV --> RULE["rule-manage 匹配<br/>按 priority_index"]
    RULE --> PA["process-application-manage<br/>SOPS 执行 / ITSM 审批"]
```

- 策略提交时弹二次确认「立即开启检测并输出风险」，属高风险操作。
- 策略升级有独立向导：`strategy-create/upgrade/:strategyId/:controlId`。
- 联表与工具均带 `version` 字段，用于检测引用方是否落后于当前版本。

## 系统接入

`new-system-manage` 与 `system-manage` 是**职责拆分并存**，共享同一份 `sideMenus`，`navName` 均为 `nweSystemManage`。

- `new-system-manage`（`/nwe-system-manage/:id?`）：接入向导 + 系统信息 + 系统诊断 + 引导页
- `system-manage`（`/system-manage`）：系统列表 + 系统详情 + 日志上报 + 采集 + 字段清洗

```mermaid
flowchart TD
    L["systemLandingPage 引导页"] -->|接入新系统| S1["Step1 注册系统信息<br/>系统ID/名称/管理员/域名 + 应用ID"]
    S1 --> S2["Step2 注册权限模型<br/>simple / complex"]
    S2 --> S3["Step3 上报日志数据"]
    S3 --> S4["Step4 接入完成"]
    L -->|选择已有系统| SL["systemList 系统列表"]
    SL --> SD["系统详情 / 系统信息 / 系统诊断"]

    S3 --> LC["log-create/:systemId"]
    LC --> C1["newlog/collector 采集器（5 步）"]
    LC --> C2["newlog/api API 上报"]
    LC --> C3["bkbase（3 步）"]
    C1 & C2 & C3 --> FC["field-cleaning 字段清洗"]
    FC --> DI["data-inspection 数据检查"]
    DI --> ST["storage-manage 数据存储"]
```

- 日志上报编辑入口有两条路由，复用同一 `log-create/index.vue`：`log-edit/dataid/:bkDataId` 与 `log-edit/collector/:collectorConfigId`。
- 采集完成后跳转 `collector-complete/:systemId/:collectorConfigId/:taskIdList`。
- 相关服务：`collector-manage`、`dataid-manage`、`meta-manage`、`storage-manage`。

## 场景（Scene）上下文

场景是贯穿全项目的横切上下文，产生三元组 `{ scene_id, scope_id, scope_type }`，`scope_type` 取值：`scene` / `system` / `cross_scene`（全部场景）/ `cross_system`（全部系统）。

```mermaid
flowchart TD
    SEL["scene-system-selector 选择"] --> MEM["setActiveSceneSelection()<br/>写入内存变量"]
    MEM --> SYNC["markSceneSelectorSwitched()<br/>+ localStorage<br/>+ syncSceneContextToUrl()"]
    SYNC --> GET["getSceneSystemParams()"]
    GET --> PR1["① 内存 activeSceneSelection"]
    GET --> PR2["② URL query"]
    GET --> PR3["③ localStorage"]
    PR1 & PR2 & PR3 --> INJ["domain/source 与 service 层<br/>逐个 API 拼参注入"]
    INJ --> API["risk / strategy / tool / meta / notice-group<br/>link-data / process-application"]
```

- 核心文件：`src/utils/assist/scene-system-params.ts`，提供 `getSceneSystemParams`、`getSceneContextQuery`、`syncSceneContextToUrl`、`setActiveSceneSelection`、`markSceneSelectorSwitched`、`resolveToolDetailScopeParams` 等。
- 取值优先级：内存 > URL query > localStorage。
- 路由守卫中的场景分流（`resolveSceneConfigSceneAccess`）：

| 条件 | 结果 |
| --- | --- |
| `manage_scene === true` | 放行并持久化该场景选择 |
| 仅 `view_scene` + 分享链接直开 | 跳转 `userLandingPage` 引导申请 |
| 仅 `view_scene` + 应用内跳转 | 自动改选第一个有管理权的场景并放行 |
| 无权限 / 接口拉取失败 | 跳转 `permissionsPage?role=manager` |

## 权限体系

```mermaid
flowchart LR
    A["第一层 角色分流<br/>sessionStorage userRole<br/>ROLE_ACCESS_MAP 规则表"] --> B["第二层 动作级鉴权<br/>components/auth 五种形态<br/>IamManageService.check"]
    B --> C["第三层 申请引导<br/>apply-permission 四形态<br/>permissionDialog()"]
    C --> D["403 兜底层<br/>响应拦截器按 payload.permission<br/>分流 page / catch / dialog"]
```

路由守卫 `beforeEach` 判定顺序：

1. 白名单放行（场景角色访问报表/工具；系统管理员访问系统页；从 `systemLandingPage` 发起的跳转）
2. `ROLE_ACCESS_MAP` 按角色遍历（一个用户可命中多套规则）
3. `meta.permission` → `IamManageService.checkAny`，失败跳 `handleManage`
4. 场景级分流 `resolveSceneConfigSceneAccess`
5. `changeConfirm()` 未保存离开确认

组件级鉴权形态：`auth-button` · `auth-component`（tsx 通用包裹）· `auth-switch` · `auth-option` · `auth-router-link`，共享 `components/auth/use-base.ts`。

## 检索 / 报表 / 工具

```mermaid
flowchart TD
    ST["storage-manage 数据存储<br/>ES 集群（super_manager）"] --> IN["系统接入 → 字段清洗 → 入库"]
    IN --> A1["analysis-manage 检索<br/>search-box + es-query"]
    IN --> T1["tool-manage-shared 工具建模"]
    IN --> R1["statement-manage 报表<br/>委托 BKVision 渲染"]

    T1 --> T2["工具类型<br/>data-search（SQL/simple）· api · bkvision · 内置"]
    T2 --> T3["tools 工具广场"]
    T3 --> U1["① 直接执行 → 结果弹窗"]
    T2 --> U2["② 字段下钻<br/>strategy step2 drill_config<br/>风险详情点击字段打开"]
    T2 --> R1
```

- 工具创建有**两个入口、一套实现**：`platform-manage/tool-manage`（平台级）与 `scene-config/tool-manege`（场景级），共同实现收敛在 `views/tool-manage-shared`，通过 `context.ts` 的 `createPlatformToolManageContext()` / `createSceneToolManageContext()` 区分数据源、删除方法、路由名与文案。
- 工具有 `creating` / `Successful` / `failed` 三态（`tool-status/`）。
- 工具广场列表与详情共用组件，通过 `keepAliveKey: 'toolsSquarePage'` 缓存。

---

> [← 文档索引](./README.md) ｜ 上一篇：[业务模块](./business-modules.md) ｜ 下一篇：[公共组件](./components.md)
