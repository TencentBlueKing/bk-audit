# 蓝鲸审计中心

本仓库包含审计数据接入、风险分析和事件处置的产品实现。

- `src/frontend/` 是 Web 前端。涉及前端时读取[前端指引](src/frontend/AGENTS.md)。
- `src/backend/` 是后端服务。涉及后端时读取[后端指引](src/backend/AGENTS.md)。跨端任务读取两份指引。
- `agent/` 存放[协作入口](agent/README.md)、技能与工具。可到项目或相应端的 `.agents/skills/` 查找已接入技能，或通过[公共 onboarding](agent/shared/skills/bk-audit-onboarding/SKILL.md) 了解能力。

执行提交、推送、创建或合入 PR/MR 前，先定位并读取本次适用的协作与提交技能，核实其要求的前置条件。技能来源或必要信息缺失时，先说明缺口并补齐，再执行受影响操作。
