# 蓝鲸审计中心 · 前端文档

> 版本：v1.19.14。Agent 入口是仓库内 `AGENTS.md`（任务路由到 skill 与本目录）。

---

## 文档地图

| 文档 | 内容 | 什么时候看 |
| --- | --- | --- |
| [项目总览](./project-overview.md) | 代码规模、技术选型、状态管理策略、工程能力 | 第一次接触项目 |
| [架构与目录](./architecture.md) | 七层架构分层、启动流程、目录结构、路径别名 | 理解代码怎么组织 |
| [功能地图](./feature-map.md) | 顶部导航、模块挂载关系、角色与可见性 | 找功能在哪儿 |
| [业务模块](./business-modules.md) | 20 个 views 模块的职责、路由与关键能力 | 接手某个模块 |
| [核心业务流程](./business-flows.md) | 风险主链路、策略链路、系统接入、场景上下文、权限、工具 | 理解业务怎么跑通 |
| [公共组件](./components.md) | 35 个顶层目录、全局注册与重点组件实现要点 | 写页面选型 |
| [Hooks 与工具函数](./hooks-and-utils.md) | 27 个组合式函数、网络层封装、utils 工具集 | 复用逻辑 |
| [领域层](./domain-layer.md) | source / service / model 三层、服务与模型清单 | 新增接口 |
| [开发约定](./conventions.md) | 路由 meta、列表页骨架、服务速查、常用命令 | 日常开发 |

---

## 30 秒速览

**规模**：584 个 Vue 组件 ｜ 275 个 TS/TSX 文件 ｜ 20 个业务模块 ｜ 35 个公共组件目录 ｜ 27 个组合式函数。

**技术栈**：Vue 3.5 + TypeScript 5.2 + Vite 8 + vue-router 4.2 + vue-i18n 11 + bkui-vue 2.0（TDesign 为辅）+ ECharts / Monaco / Quill。

**架构一句话**：`views` 业务模块 → `components` 公共组件 → `hooks`/`utils` 逻辑复用 → `domain`（service → source → model）→ 自研 `request` 网络层。

**四个必知概念**

| 概念 | 说明 |
| --- | --- |
| 风险五视图 | `risk-manage` / `handle-manage` / `processed-manage` / `attention-manege` / `scene-risk-manage` 是**同一风险实体的五个视图**，共用 `views/risk-manage/detail/index.vue`，差异仅在列表 `dataSource` |
| 场景上下文 | `scene_id` / `scope_id` / `scope_type` 三元组是全局横切维度，由 `utils/assist/scene-system-params.ts` 统一维护 |
| URL 即状态 | 筛选、分页、排序、时间范围、场景上下文全部写入 URL query，可分享可刷新恢复 |
| 领域三层 | `source`（接口定义）→ `service`（业务语义 + 模型转换）→ `model`（字段结构与默认值）；视图层只 import `@service/*` |

---

## 维护约定

- 文档按主题拆分，新增内容优先归入对应文件；单文件过长时再拆。
- 图谱统一使用 **mermaid** 代码块，保证在 Git 与文档平台均可渲染、可 diff。
- 修改源码后同步更新对应文档，尤其是 `business-modules.md`（模块清单）、`components.md`（组件清单）、`domain-layer.md`（服务清单）。
