# 后端 pre-commit 开发规范

后端以 `src/backend/.pre-commit-config.yaml` 作为唯一检查规则，项目开发依赖固定使用
`pre-commit==4.2.0`。本地提交检查暂存文件，CI 检查全部受管文件。

## 首次安装

在 `src/backend` 目录安装项目开发依赖后执行：

```bash
make install-hooks
```

该命令使用项目 `.venv/bin/pre-commit` 安装 Git 的 `pre-commit` hook。每个 clone 需要安装
一次；标准 Git worktree 与主 checkout 共用 hook。更新 `.pre-commit-config.yaml` 后可再次执行。

不建议使用 `--allow-missing-config`。它会允许配置文件不存在时跳过检查，适合通用模板，
不适合已经强制维护配置的本项目。

`pre-commit install --hook-type commit-msg` 只负责安装 `commit-msg` 阶段入口。当前配置没有
`commit-msg` 阶段的检查项，因此它不会校验提交信息，也无需安装。

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
`Backend pre-commit` 和现有单测 job 设为 required checks；本地 hook 可以被人为绕过，
分支保护才是最终强制门禁。
