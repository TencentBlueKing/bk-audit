---
name: bk-audit-version-release
description: Use when preparing a BK Audit release, writing product-facing release notes, updating release version metadata, checking release gaps, or creating a release commit for bk-audit.
---

# 蓝鲸审计中心版本发布

根据前一次发布到目标 SHA 的实际变更和人工总结，生成产品版本日志、同步前后端元数据并核对发布风险。需要交付版本文件时，使用 `release-{版本号}-notes` 分支通过 PR 合入 `main`。只整理日志草稿时无需建立分支或提交。

## 基本原则

- 版本日志以证据为准：对比前一次发布基准到已确认发布目标的 commits、diff 和文件路径，不能只照抄人工总结。
- 人工总结是输入，不是最终结论：需要检查“总结提到但 commit 证据不明显”和“commit 有变更但总结遗漏”的项。
- 版本日志面向产品侧：按用户可感知能力归类，避免暴露 hook、schema、内部占位、实现细节等低层表述。
- 本轮要求实际提交时，发布改动收敛成语义完整的 release commit；只暂存发布相关文件。

## 版本号格式

版本号使用 `主版本号.次版本号.修订号`，例如 `1.19.7`；输入可带 `V` 前缀，使用前先归一化为 `1.19.7`。notes 分支和 package.json 使用无前缀数字，后端 VERSION 与版本日志文件名按文件规则使用 `V1.19.7`。

版本日志分支固定为 `release-{版本号}-notes`，例如 `release-1.19.7-notes`，用于将日志及版本文件合入 `main`；它与正式 `release-{版本号}` 发布分支用途不同，不用发布分支承载本次 notes 改动。各文件位置和格式见 [file-patterns.md](references/file-patterns.md)。

## 必需输入

先区分只分析/撰写日志、同步版本元数据、实际提交/发布。本轮只要求日志时只产出草稿或指定日志文件，不自动更新版本号、创建分支或执行后续操作；以下流程按已确认范围取用。

- 目标版本号：如 `1.19.7` 或 `V1.19.7`
- 前一次发布基准：优先使用用户给定 commit；没有则从上一版本 release commit/tag 推断
- 发布目标 ref/SHA：用户指定的目标，或经确认的 main；记录实际 SHA
- 人工总结点：业务侧明确希望体现的功能、优化、修复
- Commit 信息：仅实际提交时需要，tracker 使用真实关联编号

信息不足时先从本地仓库推断；只有版本号、基准范围或提交目标无法确定时再问用户。

## 标准流程

### 1. 确认范围并准备 notes 分支

先区分日志草稿、版本文件更新与实际提交。只整理日志草稿时，不创建分支或 worktree。需要交付版本文件时，遵循用户指定的工作区；未指定时，先检查主仓状态和是否有其他任务正在使用该工作区。主仓干净且切换分支不会干扰其他工作时，默认在主仓基于已确认的 `main` SHA 创建 notes 分支，不需要新建 worktree。

主仓存在未提交改动，或切换分支可能影响正在进行的工作时，先保留现状，不自动 stash、覆盖或迁移改动。优先复用合适的现有工作区；如果无法安全判断能否切换，向用户说明现状，让用户选择继续使用现有工作区还是使用隔离 worktree。用户明确要求 worktree 时遵循其要求；工作区干净并不单独证明切换分支不会干扰其他任务。

创建基线是经确认的 `main` SHA；日志比较基准则是前一次发布，二者不能混用。先核对 main 所属远端及本轮选定 SHA，不能因本地分支名为 main 就认为它是目标最新版本。发布目标尚未进入 main 时，先明确业务改动与 notes 的合入顺序。

以下示例用于已经确认版本为 1.19.7、基线正确且可以安全切换的选定工作区：

```bash
git status --short --branch
git show --no-patch --format='%H %s' <main-sha>
git checkout -b release-1.19.7-notes <main-sha>
```

`<main-sha>` 必须替换为本次确认的完整 main 提交 SHA；它不是上一版本的比较基准。同名 notes 分支已存在时核对其内容再决定沿用，不覆盖或重置。

### 2. 定位对比范围

优先级：

1. 用户明确给出的基准 commit
2. 上一版本 release commit，如 `feat: release-1.19.6版本发布`
3. 上一版本 tag，如 `v1.19.6-*`
4. `release.md` 顶部的上一版本号，再用 `git log --grep` 查找 release commit

必须记录最终采用的范围，例如：

```bash
git log --oneline --decorate <base_commit>..<target_ref>
git diff --stat <base_commit>..<target_ref>
git diff --name-status <base_commit>..<target_ref>
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
- 中间问题过滤：对修复和性能补偿提交，检查是否由同一发布范围内的新增需求引入。只有同时具备提交祖先关系、变更路径或关联事项等证据，且修复仅使新能力达到预期时，才不单列为版本点；保留最终新增或优化能力。证据不足时标为“待确认”，不要自行排除。

## 一致性检查

生成草稿后必须输出检查结果，提醒用户确认：

| 检查项 | 处理方式 |
| --- | --- |
| 人工总结提到但 commit 证据不明显 | 标为“待确认”，列出总结原文 |
| commit 里有明显产品变更但总结没提 | 补入草稿或标为“可能遗漏” |
| 同一能力重复出现 | 合并成一个产品侧表述 |
| 分类可能不准 | 明确指出，例如“失败重试更像新增能力，不是修复” |
| 同版本需求引入的中间问题 | 对修复和性能补偿提交，使用 `git merge-base --is-ancestor`、文件路径和关联事项交叉确认；确认属于需求开发或联调过程的问题时，不单列日志，仅保留最终能力，并在发现记录写明排除结论和证据 |
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

从仓库根目录视角按请求范围选择：只写日志时不更新版本徽章、package.json 或 VERSION。

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

## Git 操作

notes 分支名称和创建基线按上面的标准流程执行。固定并记录 `<base_commit>..<target_ref>`，只检查和暂存本次发布文件；文件位置统一见 [文件更新规则](references/file-patterns.md)。

确认用户要求实际提交后，使用 [项目提交技能](../generate-project-commit/SKILL.md)，按前端、后端或混合范围运行检查与 hook，形成语义完整的 notes 提交。此链接按源码布局解析；单独安装发布技能时，从已确认的产品 checkout 读取 `agent/shared/skills/generate-project-commit/SKILL.md`，缺失时先报告缺口。标题使用项目当前规则与真实关联编号，不复制示例编号；不全量暂存或绕过 hook。只写草稿不进入提交步骤。

PR 的源分支是 `release-{版本号}-notes`，目标是 `main`。推送、创建 PR、合入以及正式发布分别按任务中已经明确的授权执行；缺少具体目标时先给出待执行结果和目标，不把准备 notes 当成发布授权。正式 release 分支、tag、部署不由 notes 准备自动创建。

## 验证与提交

先对明确的发布文件检查差异：

```bash
git diff --check -- <release_files>
```

规则：

- 实际提交使用上节项目提交技能，只读引用当前 checkout 的规则。
- 只暂存本次发布文件；按前端、后端或混合改动选择实际检查与 hook，不默认把后端 .venv 当作前端环境。
- 不绕过 hook，不创建或伪造需求编号。只要求准备日志时不暂存、不提交。
- `debug/`、`.env`、`.venv`、`config/local_settings.py` 不要提交。
- 提交后检查 `git status --short --branch` 和 `git log -1 --stat --oneline`。

## 合入主分支

如果用户要求合入主分支：

1. 先说明 release commit、变更文件、验证结果、待关注 checklist。
2. 按本次已明确的 push、PR 与合入授权执行；未授权的具体动作先汇报目标与验证结果。
3. 合入后核对 main 的最终 SHA、版本文件与已审定的 notes 改动；保留 PR 及验证证据。

不要在未确认的情况下直接推送或合并到主仓库主分支。

## 交付格式

最终回复必须包含：

- 版本日志摘要
- 一致性检查结论
- 环境与变更 checklist 命中项
- 已修改文件
- 验证结果
- commit hash（如果已提交）
