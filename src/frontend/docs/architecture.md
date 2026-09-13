# 架构与目录

> [← 文档索引](./README.md) ｜ 上一篇：[项目总览](./project-overview.md) ｜ 下一篇：[功能地图](./feature-map.md)

## 分层图谱

```mermaid
flowchart TD
    subgraph L6["L6 入口层"]
        A1["main.ts 应用装配"] --- A2["app.vue + layout.vue"] --- A3["i18n 中英文"] --- A4["平台配置 / 水印 / Aegis"]
    end
    subgraph L5["L5 路由层"]
        B1["router/index.ts 路由表<br/>19 个业务模块路由"] --- B2["beforeEach 全局守卫<br/>角色分流 / IAM / 场景 / 离开确认"] --- B3["meta 约定<br/>keepAlive / navName / permission"]
    end
    subgraph L4["L4 视图层 views/"]
        C1["风险域<br/>risk / handle / processed / attention"] --- C2["配置域<br/>strategy / rule / link-data / notice"] --- C3["接入域<br/>system / new-system / storage"] --- C4["分析域<br/>analysis / statement / tools"]
    end
    subgraph L3["L3 组件层 components/"]
        D1["35 个组件目录<br/>23 个全局注册"] --- D2["bkui-vue + TDesign"] --- D3["Monaco / Quill / ECharts / xlsx"] --- D4["蓝鲸生态组件"]
    end
    subgraph L2["L2 逻辑层"]
        E1["hooks/ 27 个组合式函数"] --- E2["utils/ 工具集"] --- E3["mitt 事件总线"] --- E4["directives/ 指令"]
    end
    subgraph L1["L1 领域层 domain/"]
        F1["service/ 29 个<br/>拼参 + 数据转 Model"] --- F2["source/ 接口定义<br/>ModuleBase: url + method"] --- F3["model/ 23 个目录<br/>class + 默认值"]
    end
    subgraph L0["L0 网络层"]
        G1["request/index.ts 门面"] --- G2["拦截器<br/>401 登录 / 403 权限 / Blob 下载"] --- G3["CSRF / GET 缓存 / cancelToken"] --- G4["axios → 后端 /api/v1"]
    end

    L6 --> L5 --> L4 --> L3 --> L2 --> L1 --> L0
```

依赖方向自上而下：上层只依赖紧邻下层的约定（通过路径别名导入），不存在反向引用。

各层职责：

| 层 | 目录 | 职责 |
| --- | --- | --- |
| L6 入口层 | `src/main.ts`、`app.vue`、`layout.vue` | 应用装配、全局注册、布局骨架、语言与平台配置 |
| L5 路由层 | `src/router/` | 路由表、角色分流、IAM 鉴权、场景分流、离开确认 |
| L4 视图层 | `src/views/` | 20 个业务模块的页面与模块内组件 |
| L3 组件层 | `src/components/` | 跨模块复用的公共组件与第三方 UI 封装 |
| L2 逻辑层 | `src/hooks/`、`src/utils/` | 请求状态机、URL 读写、工具函数、事件总线、指令 |
| L1 领域层 | `src/domain/` | 接口定义、业务语义、领域模型 |
| L0 网络层 | `src/utils/request/` | axios 封装、拦截器、缓存、错误处理 |

## 启动流程

```mermaid
flowchart LR
    A["main.ts"] --> B["Promise.all 并发<br/>config() / watermark() / getUserPermission()"]
    B -->|"全部成功"| C["createApp 装配<br/>use BkuiVue / i18n / Router<br/>注册 23 个全局组件 + 2 个指令"]
    B -->|"失败且非 401"| X["渲染 exception.vue"]
    B -->|"401 未登录"| Y["直接 return<br/>由 login-modal 接管"]
    C --> D["旁路初始化<br/>Aegis / 水印 / warmAgents<br/>失败不阻断"]
    D --> E["mount('#app')"]
```

- 启动配置写入 `sessionStorage['BK_AUDIT_CONFIG']`，含 `super_manager`、`aegis_id`、`agent_auth`、`metric` 等字段。
- `config.super_manager === true` 时，路由表动态追加 `StorageManage`（数据存储模块）。
- 全局注册的 23 个组件：`ApplyPermissionCatch`、`AuditForm`、`AuditIcon`、`AuditPopconfirm`、`AuditRouterView`、`AuditSideslider`、`AuditUserSelectorTenant`、`AuthButton`、`AuthComponent`、`AuthOption`、`AuthSwitch`、`AuthRouterLink`、`AuthCollapsePanel`、`RelationShip`、`RenderList`、`TdesignList`、`RenderSensitivityLevel`、`ScrollFaker`、`SkeletonLoading`、`SmartAction`、`DatePicker`（来自 `@blueking/date-picker`）、`SelectVerify`、`SearchBox`。
- 全局注册的 2 个指令：`bk-tooltips`、`cursor`。

## 目录结构

```
src/frontend/
├── index.html
├── vite.config.ts              # 13 个路径别名、构建分包、dev server 配置
├── package.json
├── server/                     # Express 静态服务（esbuild 打包）
├── static/                     # publicDir
├── lib/                        # bk-icon 图标库
└── src/
    ├── main.ts                 # 应用装配入口
    ├── app.vue                 # 根组件：config-provider + layout + 页头插槽
    ├── layout.vue              # 布局骨架：顶部 7 大导航 + 侧边菜单 + 面包屑
    ├── exception.vue           # 启动失败兜底页
    │
    ├── views/                  # 业务模块（20 个；`tool-manage-shared` 无独立路由）
    ├── components/             # 公共组件（35 个顶层目录）
    ├── hooks/                  # 组合式函数（27 个）
    ├── utils/                  # 工具函数
    │   ├── assist/             #   20+ 子模块（dom / url / 时间 / 权限 / 场景参数 …）
    │   ├── request/            #   axios 封装（lib + middleware）
    │   └── validator.ts / getFieldTypeIcon.ts / format-strategy-name.ts …
    │
    ├── domain/
    │   ├── source/             # 接口定义层：class Xxx extends ModuleBase
    │   ├── service/            # 业务语义层（29 个）
    │   └── model/              # 领域模型（23 个目录）
    │
    ├── router/index.ts         # 路由表 + 角色访问规则 + 全局守卫
    ├── language/               # i18n
    ├── css/                    # reset.css / tokens.css / common.css
    ├── directives/cursor/      # v-cursor 指令
    └── images/                 # 静态图片（field-type/*.png 由 import.meta.glob 预加载）
```

## 路径别名

在 `vite.config.ts` 中定义，全项目统一使用别名导入：

| 别名 | 实际路径 |
| --- | --- |
| `@` | `src/` |
| `@views` | `src/views` |
| `@components` | `src/components` |
| `@service` | `src/domain/service` |
| `@model` | `src/domain/model` |
| `@hooks` | `src/hooks` |
| `@utils` | `src/utils` |
| `@router` | `src/router` |
| `@directives` | `src/directives` |
| `@css` | `src/css` |
| `@language` | `src/language` |
| `@images` | `src/images` |
| `@lib` | `lib/`（工程根目录） |

> 视图层统一通过 `@service/*` 取数，不直接引用 `@utils/request`。

---

> [← 文档索引](./README.md) ｜ 上一篇：[项目总览](./project-overview.md) ｜ 下一篇：[功能地图](./feature-map.md)
