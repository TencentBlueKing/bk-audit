---
name: bk-audit-version-release
description: Use when preparing a BK Audit version release, updating release version metadata or changelogs, or using the project-standard version release automation.
---

# 蓝鲸审计中心版本发布

自动化版本发布流程，包括版本号更新、版本日志创建和 Git 提交。

## 工作流程

1. **创建 Git 分支**：从 main 分支创建并切换到新的 release 分支
2. **更新版本号**：修改以下文件中的版本号
   - `release.md` - 在顶部添加新版本日志
   - `readme.md` - 更新版本号徽章
   - `readme_en.md` - 更新版本号徽章
   - `src/frontend/package.json` - 更新 version 字段
   - `src/backend/VERSION` - 更新版本号
3. **创建版本日志**：在 `src/backend/version_md/` 目录下创建中英文版本日志文件
4. **提交更改**：使用提供的 commit 信息提交所有更改

## 使用方法

### 必需参数

- **版本号**：例如 `release-1.19.2` 或 `1.19.2`
- **版本日志内容**：中文版本日志内容，例如 `[ 新增 ] 审计工具新增 API 工具`
- **Commit 信息**：Git commit 信息，例如 `feat: 审计中心-V1.19.2版本发布 --story=129850328`

### 版本日志格式

版本日志文件命名格式：`V{版本号}_{日期}_zh-cn.md` 和 `V{版本号}_{日期}_en.md`

日期格式：`YYYYMMDD`（例如：20260108）

中文版本日志模板：

```markdown
## V{版本号} 版本更新日志

- {版本日志内容}
```

英文版本日志模板：

```markdown
## Version {版本号} Release Notes

- [ NEW ] {英文翻译的版本日志内容}
```

## 文件更新规则

### release.md

在文件顶部添加新的版本日志部分，格式：

```markdown
## V{版本号} 版本更新日志

- {版本日志内容}

## V{上一个版本号} 版本更新日志
...
```

### readme.md 和 readme_en.md

更新版本号徽章中的版本号：

```markdown
[![Release Version](https://img.shields.io/badge/release-{版本号}-brightgreen.svg)]
```

### src/frontend/package.json

更新 `version` 字段：

```json
"version": "{版本号}",
```

### src/backend/VERSION

更新版本号：

```
V{版本号}
```

## 自动化脚本

使用 `scripts/release_version.py` 脚本可以自动化执行整个流程。脚本接受以下参数：

- `--version`: 版本号（必需）
- `--changelog`: 中文版本日志内容（必需）
- `--changelog-en`: 英文版本日志内容（可选，推荐提供）
- `--commit`: Commit 信息（必需）
- `--date`: 日期（可选，默认为当前日期）

示例：

```bash
python scripts/release_version.py --version 1.19.2 --changelog "[ 新增 ] 审计工具新增 API 工具" --changelog-en "[ NEW ] Added API tools for audit utility" --commit "feat: 审计中心-V1.19.2版本发布 --story=129850328"
```

## 注意事项

- 确保当前工作目录是项目根目录
- 确保 main 分支是最新的
- 版本号格式应遵循语义化版本规范（例如：1.19.2）
- Commit 信息应遵循项目规范，包含类型前缀和 story ID
