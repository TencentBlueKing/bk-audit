# 蓝鲸审计中心

本仓库包含审计数据接入、风险分析和事件处置的产品实现。

- `src/frontend/` 是 Web 前端。涉及前端时读取[前端指引](src/frontend/AGENTS.md)。
- `src/backend/` 是后端服务。涉及后端时读取[后端指引](src/backend/AGENTS.md)。跨端任务读取两份指引。
- 首次接入、新建 worktree 或不确定该用哪个流程时，从[公共 onboarding](agent/shared/skills/bk-audit-onboarding/SKILL.md)了解能力、选择入口并补齐本次所需条件。已明确适用流程时，直接读对应技能；索引见[协作入口](agent/README.md)。
- 涉及已接入的内部流程时，先看仓库根的本地 `.agents/README.md`（如有）、已发现的技能或当前端的 `skills-lock.json`，确定内部维护源。工作区与个人补充按所属端的 AGENTS 读取。

执行提交、推送、创建或合入 PR/MR 前，先定位并读取本次适用的协作与提交技能，核实其要求的前置条件。技能来源或必要信息缺失时，先说明缺口并补齐，再执行受影响操作。
