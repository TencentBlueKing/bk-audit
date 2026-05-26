# 文件更新模式参考

本文档描述了版本发布时需要更新的文件及其更新模式。

## 文件列表

### 1. release.md

**位置**: 项目根目录

**更新方式**: 在文件顶部插入新的版本日志部分

**格式**:
```markdown
## V{版本号} 版本更新日志

- [ 新增 ] 功能描述
- [ 优化 ] 优化描述
- [ 修复 ] 修复描述

## V{上一个版本号} 版本更新日志
...
```

**示例**:
```markdown
## V1.19.2 版本更新日志

- [ 新增 ] 审计工具新增 API 工具

## V1.19.1 版本更新日志
...
```

### 2. readme.md / readme_en.md

**位置**: 项目根目录

**更新方式**: 更新版本号徽章中的版本号

**查找模式**:
```markdown
[![Release Version](https://img.shields.io/badge/release-{旧版本号}-brightgreen.svg)]
```

**替换为**:
```markdown
[![Release Version](https://img.shields.io/badge/release-{新版本号}-brightgreen.svg)]
```

### 3. src/frontend/package.json

**位置**: `src/frontend/package.json`

**更新方式**: 更新 `version` 字段

**查找模式**:
```json
"version": "{旧版本号}",
```

**替换为**:
```json
"version": "{新版本号}",
```

### 4. src/backend/VERSION

**位置**: `src/backend/VERSION`

**更新方式**: 替换整个文件内容

**格式**:
```
V{版本号}
```

**示例**:
```
V1.19.2
```

### 5. 版本日志文件

**位置**: `src/backend/version_md/`

**文件命名格式**:
- 中文: `V{版本号}_{日期}_zh-cn.md`
- 英文: `V{版本号}_{日期}_en.md`

**日期格式**: `YYYYMMDD` (例如: 20260108)

**中文版本日志格式**:
```markdown
## V{版本号} 版本更新日志

- [ 新增 ] 功能描述
```

**英文版本日志格式**:
```markdown
## Version {版本号} Release Notes

- [ NEW ] Feature description
```

## 版本号格式

- 遵循语义化版本规范: `主版本号.次版本号.修订号`
- 示例: `1.19.2`
- 分支名格式: `release-{版本号}` (例如: `release-1.19.2`)

## Git 操作

1. **创建分支**: 从 `main` 分支创建新分支 `release-{版本号}`
2. **提交信息格式**: `feat: 审计中心-V{版本号}版本发布 --story={story_id}`
3. **提交后**: 需要手动推送分支并创建 Pull Request

