# 审计 Agent 协作入口

按任务范围进入下一层；工程说明和可执行配置由对应入口定位。

项目启动约定见根 [AGENTS.md](../AGENTS.md)。从根目录开展端内任务时，也要读取对应 `src/backend/AGENTS.md` 或 `src/frontend/AGENTS.md`。接入扩展能力时，可通过 onboarding 定位已确认来源。

| 范围 | 入口 | 职责 |
| --- | --- | --- |
| 跨端 | [shared](shared/README.md) | 上手与能力选配、提交、版本日志及 skills/工具/MCP 分类 |
| 后端 | [backend](backend/README.md) | 后端工程规范、IAM、AI 评估与提交校验工具 |
| 前端 | [frontend](frontend/README.md) | 前端开发、类型、lint 与提交配置 |
| 维护 | [架构与维护约定](architecture.md) | 新增、调整或删除能力时的归属、引用与验证 |

先按用户意图选择实际技能，流程咨询也应查阅维护源；技能和 references 按需读取。已有环境直接开展任务；首次接入、准备新 worktree 或发现能力缺口时，再由 shared 的 onboarding 诊断与准备。
