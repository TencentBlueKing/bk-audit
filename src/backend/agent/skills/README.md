# BK Audit Skills / 蓝鲸审计中心技能库

本目录维护蓝鲸审计中心开发过程中可复用的 Codex Skills，覆盖项目约定、标准流程、自动化脚本和高风险操作清单。

## 技能列表

### [新增 IAM 资源类型](adding-iam-resource-type/SKILL.md)

- **路径**：`adding-iam-resource-type/`
- **简介**：新增 IAM 资源类型时的完整修改清单。
- **适用场景**：
  - 新增受 IAM 管控的资源类型。
  - 注册资源反向拉取 provider。
  - 补充 IAM migration、`initial.json`、provider URL 和资产同步配置。
  - 排查 `ResourceNotRegistered` / `ResourceNotExistError`。

### [版本发布](bk-audit-version-release/README.md)

- **路径**：`bk-audit-version-release/`
- **简介**：自动化版本发布流水线。
- **主要功能**：
  - 创建 release 分支。
  - 批量更新版本号文件，包括 `release.md`、`readme.md`、`readme_en.md`、`src/frontend/package.json`、`src/backend/VERSION`。
  - 生成中英文版本日志文件。
  - 按规范提交版本发布变更。

### [生成项目 Commit](generate-project-commit/SKILL.md)

- **路径**：`generate-project-commit/`
- **简介**：生成、校验并提交符合 bk-audit 规范的 commit message。
- **主要功能**：
  - 根据暂存区或指定文件归纳提交范围。
  - 渲染并校验 TAPD / GitHub tracker 格式。
  - 约束正文 bullet 风格，避免把实现细节写进 commit message。
  - 配合项目 pre-commit 流程完成实际提交。

## 目录结构

```text
agent/skills/
├── README.md
├── adding-iam-resource-type/
│   └── SKILL.md
├── bk-audit-version-release/
│   ├── README.md
│   ├── SKILL.md
│   ├── references/
│   └── scripts/
└── generate-project-commit/
    ├── SKILL.md
    └── scripts/
```

## 使用方式

按任务选择对应 skill，优先阅读该目录下的 `SKILL.md`；如 skill 包含 `README.md`、`references/` 或 `scripts/`，按文档说明继续使用。
