# 后端 pre-commit 开发规范

后端以 `src/backend/.pre-commit-config.yaml` 作为唯一检查规则，项目开发依赖固定使用
`pre-commit==4.2.0`。本地提交检查暂存文件，CI 检查全部受管文件。

## 首次安装

在 `src/backend` 目录安装项目开发依赖后执行：

```bash
make install-hooks
```

该命令使用项目 `.venv/bin/pre-commit` 安装 Git 的 `pre-commit` 和 `commit-msg` hook。
每个 clone 需要安装一次；标准 Git worktree 与主 checkout 共用 hook。
更新 `.pre-commit-config.yaml` 后可再次执行，不需要重复维护本机 `.git/hooks` 内容。

不建议使用 `--allow-missing-config`。它会允许配置文件不存在时跳过检查，适合通用模板，
不适合已经强制维护配置的本项目。

提交标题检查通过后端配置中的 local hook 运行
`agent/skills/generate-project-commit/scripts/commit_message.sh`，只依赖 `sh`、`awk` 和 Git。
校验器不使用 `.venv` 路径，也不要求启动 Django。pre-commit 本身仍需要安装环境，
它生成的 Git 入口会记录当前安装器的 Python 路径；迁移虚拟环境后重新运行安装命令即可。

本次只接入后端：暂存区含 `src/backend` 改动时校验标题，混合前后端提交也会校验；
纯前端及其他非后端改动跳过。无暂存差异的 amend/reword 等仍校验，避免通过改标题漏检。
worktree 共用入口，但会读取当前 worktree 的配置和暂存区；尚未接入的旧分支不会自动获得规则。

如果本机设置了 `core.hooksPath`（例如前端 Husky 安装设置），pre-commit 会拒绝安装。
先检查配置来源和现有 hook，再明确选择使用哪套入口；不要静默覆盖、自动 unset 或修改前端配置。

## 提交标题规则

普通标题使用 `<type>: <summary> #<issue>` 或 `<type>: <summary> --<TAPD key>=<数字>`，
tracker 位于标题末尾。允许 `feat fix docs style refactor perf test chore`，摘要不能为空。
常用 TAPD key 是 `story` 和 `bug`；格式合法不代表需求存在或归属正确。
合并标题 `Merge ...` 允许不带 tracker。

正文可选，推荐空行后写概括性的 `- ` bullet。hook 不额外强制正文格式。
单独验证已有 message 或检查指定历史范围，可在后端目录执行：

```bash
sh agent/skills/generate-project-commit/scripts/commit_message.sh validate --message-file /tmp/commit-message.txt
sh agent/skills/generate-project-commit/scripts/commit_message.sh check-range <base>..HEAD
```

手动验证合并标题时加 `--allow-merge`。历史检查不会补写需求号或改写提交。
本地 hook 不扫描既有历史；修改历史提交后应使用明确的范围检查，而非只检查最新提交。

## 日常开发

只暂存本次改动，不要执行 `git add .`：

```bash
git add path/to/changed_file.py
make quality
git commit
```

`make quality` 和提交 hook 默认只检查 Git 暂存区。格式器修改文件时，本次检查会失败；请
review 修改、重新暂存，再次提交。禁止使用 `git commit --no-verify` 绕过检查。

常用入口：

```bash
make quality      # 只检查暂存文件，等价于提交 hook
make quality-all  # 检查全部文件，本地复现 CI
make test         # 运行后端全量单元测试
make check        # 检查暂存文件并运行全量单元测试
```

## CI 与合并约束

GitHub Actions 的 `Backend pre-commit` job 会在后端相关 PR 和 main 推送时执行
`pre-commit run --all-files --show-diff-on-failure`。仓库管理员应在 main 分支保护规则中将
`Backend pre-commit` 和现有单测 job 设为 required checks。该 job 检查文件质量，
不会因新增本地 `commit-msg` hook 自动扫描提交历史；历史标题仍需使用明确范围检查或
对应的上游提交门禁，本次不修改 CI 流程。
本地 hook 可以被人为绕过，
分支保护才是最终强制门禁。
