---
name: bk-audit-version-release
description: Use when preparing a BK Audit release, writing product-facing release notes, updating release version metadata, checking release gaps, or creating a release commit for bk-audit.
---

# 蓝鲸审计中心版本发布

用于从 `main` 的实际提交和人工总结中生成产品侧版本日志，并同步版本元数据、提醒发布风险，最后在版本日志 feature 分支上形成一个可合入主分支的 release commit。

## 基本原则

- 版本日志以证据为准：必须对比前一次发布版本到当前 `main` 的 commits、diff 和文件路径，不能只照抄人工总结。
- 人工总结是输入，不是最终结论：需要检查“总结提到但 commit 证据不明显”和“commit 有变更但总结遗漏”的项。
- 版本日志面向产品侧：按用户可感知能力归类，避免暴露 hook、schema、内部占位、实现细节等低层表述。
- 发布改动必须收敛成单个语义完整的 release commit；只暂存发布相关文件。
- 信息量较大的发布任务需要维护计划、发现和进展，避免长任务丢上下文；这些文件不提交。
- commit 范围较大或需要多视角取证时，可以使用只读 subagent 拆分“代码链路、风险配置、测试证据、文档质检”，主 agent 必须二次复核后再落结论。
- 不要直接运行当前自动化脚本完成全流程。现有脚本会切分支、拉取、`git add -A` 并 `--no-verify` 提交，和项目规范冲突；除非先修正脚本，否则按本 skill 手动执行文件规则。

## 必需输入

- 目标版本号：如 `1.19.7` 或 `V1.19.7`
- 前一次发布基准：优先使用用户给定 commit；没有则从上一版本 release commit/tag 推断
- 当前发布目标：通常为当前最新 `main`
- 人工总结点：业务侧明确希望体现的功能、优化、修复
- Commit 信息：如 `feat: release-1.19.7版本发布 --story=xxx`

信息不足时先从本地仓库推断；只有版本号、基准范围或提交目标无法确定时再问用户。

## 标准流程

### 1. 建立版本日志 feature 分支

从最新 `main` 新建版本日志 feature 分支，避免把发布日志混入业务分支；该分支后续通过 PR 或确认后的合并进入 `main`。

```bash
git status --short --branch
git checkout main
git fetch tencent
git merge --ff-only tencent/main
git checkout -b codex/release-1.19.7-notes
```

如果当前工作区有未提交改动，先确认这些改动是否属于本次发布；不要自动 stash 或覆盖用户改动。

### 2. 定位对比范围

优先级：

1. 用户明确给出的基准 commit
2. 上一版本 release commit，如 `feat: release-1.19.6版本发布`
3. 上一版本 tag，如 `v1.19.6-*`
4. `release.md` 顶部的上一版本号，再用 `git log --grep` 查找 release commit

必须记录最终采用的范围，例如：

```bash
git log --oneline --decorate <base_commit>..main
git diff --stat <base_commit>..main
git diff --name-status <base_commit>..main
```

### 3. 归并产品侧版本点

结合 commit 标题、变更文件和人工总结，归并为三类：

- `新增`：新能力、新入口、新接口、新流程、新可观测能力、失败重试能力等
- `优化`：已有能力的体验、性能、交互、展示、查询、筛选、导出、权限范围优化
- `修复`：缺陷修正、异常状态修复、错误展示修复、误触发修复

写法要求：

- 一条日志表达一个产品能力，不要一条 commit 一条日志。
- 合并重复项，例如“历史分析报告及导出任务支持失败重试”。
- 对“新增/优化/修复”分类有疑问时，优先看用户感知：用户获得新操作能力通常归 `新增`。
- 避免低层实现词：`hook`、`MCP schema`、`占位清理`、`接口参数增加`，除非这些就是对外能力。

## 一致性检查

生成草稿后必须输出检查结果，提醒用户确认：

| 检查项 | 处理方式 |
| --- | --- |
| 人工总结提到但 commit 证据不明显 | 标为“待确认”，列出总结原文 |
| commit 里有明显产品变更但总结没提 | 补入草稿或标为“可能遗漏” |
| 同一能力重复出现 | 合并成一个产品侧表述 |
| 分类可能不准 | 明确指出，例如“失败重试更像新增能力，不是修复” |
| 后端、前端、中英文日志不一致 | 修改到一致后再提交 |

需要保留证据路径：commit hash、文件路径或 diff 统计，方便用户快速复核。

## 变更与环境 Checklist

根据 diff 文件路径提醒发布关注点。命中即提醒，未命中可说明“未发现”。

| 关注点 | 典型文件或信号 | 发布提醒 |
| --- | --- | --- |
| 环境变量/配置 | `config/`, `settings.py`, `.env`, `app_desc.yaml` | 是否需要新增环境变量、默认值、部署配置 |
| 数据库变更 | `migrations/`, model 变更 | 是否需要迁移、回滚、数据兼容 |
| 依赖变更 | `pyproject.toml`, `pdm.lock`, `package.json`, lock 文件 | 是否需要重新构建镜像、前端依赖安装 |
| API 网关 | `support-files/apigw/` | 是否需要同步网关资源、权限、文档 |
| 异步/定时任务 | `tasks.py`, management commands, celery/periodic 配置 | 是否需要 worker、beat、队列或补偿任务关注 |
| 权限/场景隔离 | IAM、permission、scene、auth 相关文件 | 是否需要授权模型、存量权限、灰度验证 |
| 观测/监控 | `monitor`, `observability`, metrics, logging | 是否需要指标、告警、日志字段确认 |
| 国际化 | `locale/`, `language/lang/` | 是否需要编译翻译或检查中英文文案 |

## 需要更新的文件

从仓库根目录视角：

- `release.md`：在顶部插入中文版本日志
- `readme.md`：更新 release badge
- `readme_en.md`：更新 release badge
- `src/frontend/package.json`：更新 `version`
- `src/backend/VERSION`：更新 `V{version}`
- `src/backend/version_md/V{version}_{YYYYMMDD}_zh-cn.md`
- `src/backend/version_md/V{version}_{YYYYMMDD}_en.md`

日期使用当前日期，格式 `YYYYMMDD`。

中文模板：

```markdown
## V1.19.7 版本更新日志

### 新增

- [ 新增 ] ...

### 优化

- [ 优化 ] ...

### 修复

- [ 修复 ] ...
```

英文模板：

```markdown
## Version 1.19.7 Release Notes

### New Features

- [ NEW ] ...

### Optimizations

- [ OPTIMIZATION ] ...

### Fixed

- [ FIXED ] ...
```

如果某一类没有内容，不要强行保留空标题；以本次实际内容为准。

## 验证与提交

提交前必须执行：

```bash
git diff --check -- <release_files>
git add <release_files>
.venv/bin/pre-commit run
git diff --cached --stat
git commit -m "feat: release-1.19.7版本发布 --story=135736074"
```

规则：

- 只 `git add` 本次发布文件，不要 `git add .` 或 `git add -A`。
- 使用项目自带 `.venv/bin/pre-commit`。
- 不要用 `--no-verify`。
- `debug/`、`.env`、`.venv`、`config/local_settings.py` 不要提交。
- 提交后检查 `git status --short --branch` 和 `git log -1 --stat --oneline`。

## 合入主分支

如果用户要求合入主分支：

1. 先说明 release commit、变更文件、验证结果、待关注 checklist。
2. 等用户确认后再 push、创建 PR 或合入。
3. 合入后确认 `main` 最新提交包含 release commit。

不要在未确认的情况下直接推送或合并到主仓库主分支。

## 交付格式

最终回复必须包含：

- 版本日志摘要
- 一致性检查结论
- 环境与变更 checklist 命中项
- 已修改文件
- 验证结果
- commit hash（如果已提交）
