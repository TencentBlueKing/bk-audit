---
name: generate-project-commit
description: Generate, validate, or commit bk-audit backend changes using its shell title validator and local hooks.
---

# 生成项目 Commit

## Core Rule

只处理用户期望提交的后端内容。不要 `git add .`，不要把未确认的工作区改动带进 commit。
规则与脚本保持在 `src/backend`，不为前端安装 hook、不修改全局 Git 配置。
安装和范围隔离详见后端 [pre-commit 说明](../../../docs/pre-commit.md)。

## Workflow

1. 确认提交范围：
   - 用户明确给了文件/模块/需求：只看这些内容。
   - 用户只说“帮我提交”：先看 `git status --short`，若存在多个不相关变更，询问要提交哪些文件。
   - 已有 staged 内容：优先基于 `git diff --cached` 生成；若 staged 与用户描述不一致，先指出差异。

2. 收集上下文：
   - 用 `git diff --cached --stat` / `git diff --cached` 查看已暂存内容。
   - 对未暂存但用户明确要求提交的文件，用 `git diff -- <file>` 查看。
   - 需要参考历史风格时运行：

```bash
git log -n 20 --pretty=format:"%s"
```

3. 生成 commit 内容：
   - AI 先归纳 `type`、标题、tracker、正文 bullet。
   - 用 `scripts/commit_message.sh validate` 校验标题；该脚本是唯一标题规则来源。
   - 可继续用 `scripts/commit_message.py render` 生成 message；Python 入口会委托 shell 校验。
   - 正文可选，推荐总览性 bullet，不写代码实现细节。

4. 用户明确要求实际提交时：
   - 只 `git add` 本次涉及文件。
   - 按项目要求运行 `.venv/bin/pre-commit run`。
   - pre-commit 改了文件后，重新检查 diff，必要时再次 `git add` 本次涉及文件。
   - 使用校验通过的完整 commit message 执行 `git commit`。
   - 初次接入时执行 `make install-hooks`，安装 `pre-commit` 和 `commit-msg` 两个入口。
     安装仍使用项目 `.venv/bin/pre-commit`；标题校验通过 sh 执行，不硬编码 Python 路径。
   - hook 在含后端改动、混合提交或无暂存差异的 message 改写时校验；纯前端提交跳过。
     遇到 `core.hooksPath` 冲突时先检查来源，不自动 unset 或覆盖其他工具。

## Commit Message Format

允许的首行格式：

```text
<type>: <summary> #<github_issue_id>
<type>: <summary> --<tapd_key>=<numeric_tapd_id>
Merge ...
```

`type` 只能使用：

```text
feat fix docs style refactor perf test chore
```

常用选择：

- `feat`: 新功能、需求交付
- `fix`: 缺陷修复
- `refactor`: 重构，无业务行为变化
- `perf`: 性能优化
- `test`: 测试补充或调整
- `docs`: 文档
- `chore`: 构建、配置、依赖、脚本、杂项
- `style`: 格式或静态样式，不改变逻辑

TAPD 示例：

```text
feat: 审计中心支持场景隔离-业务模块更改 --story=133356995
```

GitHub 示例：

```text
fix: 修复报表删除残留收藏关系 #1234
```

不要在 tracker 后追加额外说明。历史中出现的 `--story=133356995 回填历史报表状态` 属于不合规首行，应改为把说明放到正文 bullet。

## Validation

不要复制正则规则。以下命令从 `src/backend` 执行。可选的 Python 渲染入口：

```bash
.venv/bin/python agent/skills/generate-project-commit/scripts/commit_message.py render \
  --type feat \
  --summary "审计中心支持场景隔离-业务模块更改" \
  --tracker=--story=133356995 \
  --body "收紧场景视角资源过滤，避免通过场景关联系统命中系统授权资源" \
  --body "补充场景过滤回归测试"
```

校验已有 message：

```bash
sh agent/skills/generate-project-commit/scripts/commit_message.sh validate --message-file /tmp/commit-message.txt
```

检查最近 20 条历史提交格式：

```bash
sh agent/skills/generate-project-commit/scripts/commit_message.sh check-log -n 20
```

修正历史后优先检查明确范围：

```bash
sh agent/skills/generate-project-commit/scripts/commit_message.sh check-range <base>..HEAD
```

普通提交不要生成 `Merge` 类型；合并标题只在历史检查或显式 `--allow-merge` 时允许。
hook 检查当前 message，不扫描既有历史；格式校验不验证 TAPD/GitHub 中实际关联是否存在。

## Body Style

正文 bullet 写“发生了什么”和“影响范围”，不要写“怎么改代码”。

推荐：

```text
feat: 审计中心支持场景隔离-业务模块更改 --story=133356995

- 收紧场景视角资源过滤，避免通过场景关联系统命中系统授权资源
- 删除报表时同步清理分组项与收藏关系
- APIGW 工具执行/详情拦截未发布工具并返回明确异常
- 补充场景过滤、报表删除、APIGW 未发布工具回归测试
```

避免：

```text
- 在 get_queryset 里加了 if 判断
- 修改了 xxx.py 第 42 行
- 调整变量名
```

## Output Rules

如果用户只要求生成 commit，输出一个可直接使用的 commit message 代码块。

如果用户要求实际提交，先简短列出将提交的文件，确认范围明确后执行；完成后报告 commit hash、首行 message、pre-commit 结果。
