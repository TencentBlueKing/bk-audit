# 蓝鲸审计中心版本发布工具 (BK Audit Version Release)

本工具旨在自动化蓝鲸审计中心（BK Audit）的版本发布流程，通过脚本自动处理繁琐的版本号更新、日志创建和代码提交工作，确保发布过程的规范性和效率。

## 📋 功能特性

该 Skill 包含自动化脚本和规范文档，主要完成以下工作流：

1. **分支管理**：自动从 `main` 分支创建并切换到新的 `release` 分支。
2. **全量版本号更新**：自动修改以下文件中的版本信息：
    * `release.md`: 顶部追加新版本日志。
    * `readme.md` & `readme_en.md`: 更新 Release Badge 版本号。
    * `src/frontend/package.json`: 更新前端 `version` 字段。
    * `src/backend/VERSION`: 覆盖更新后端版本标识。
3. **日志生成**：在 `src/backend/version_md/` 自动生成符合规范的中英文版本日志文件（`YYYYMMDD` 日期格式）。
4. **Git 提交**：自动暂存所有更改并按照规范提交 Commit。

## 📂 目录结构

* **`scripts/`**: 包含核心自动化脚本 `release_version.py`。
* **`references/`**: 包含 `file-patterns.md`，记录了各文件版本号的正则匹配模式和修改规则。
* **`SKILL.md`**: 原始技能定义的详细元数据。

## 🚀 使用指南

### 前置条件

* 确保在项目根目录下运行。
* 确保 `git` 状态干净且处于最新状态。

### 运行自动化脚本

使用 `scripts/release_version.py` 脚本即可一键完成发布准备。

**命令格式：**

```bash
python skills/bk-audit-version-release/scripts/release_version.py \
  --version <版本号> \
  --changelog "<中文更新日志>" \
  --changelog-en "<英文更新日志>" \
  --commit "<Git提交信息>"
```

**示例：**

```bash
python skills/bk-audit-version-release/scripts/release_version.py \
  --version 1.19.2 \
  --changelog "[ 新增 ] 审计工具新增 API 工具" \
  --changelog-en "[ NEW ] Added API tools for audit utility" \
  --commit "feat: 审计中心-V1.19.2版本发布 --story=129850328"
```

### 参数说明

| 参数 | 说明 | 示例 |
| :--- | :--- | :--- |
| `--version` | **必填**。发布的版本号。 | `1.19.2` 或 `release-1.19.2` |
| `--changelog` | **必填**。中文版本日志主要内容。 | `[ 优化 ] 提升搜索性能` |
| `--changelog-en` | 选填。英文版本日志内容。若不填则默认使用中文。 | `[ Optimization ] Improved search performance` |
| `--commit` | **必填**。符合团队规范的 Commit Message。 | `feat: V1.19.2 发布` |
| `--date` | 选填。指定发布日期 (YYYYMMDD)，默认为当天。 | `20260112` |

## ⚠️ 注意事项

1. **英文日志翻译**：脚本会自动生成英文版日志文件 (`_en.md`)，但内容默认填充为中文，**发布前请手动修改为英文**。
2. **后续操作**：脚本执行完毕后，您仍需手动执行 `git push` 并创建 Pull Request。
