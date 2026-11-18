---
name: generate-project-commit
description: 为 bk-audit 前后端整理提交范围、生成提交信息，并按改动端选择已有校验和 hook。生成或审查 message、用户明确要求实际提交时使用；不统一两端规则，不创建需求或自动推送。
---

# 审计项目提交

前后端共用范围识别与提交信息整理；各端标题规则和工具保持独立。本技能可以安装在仓库外，下面路径均相对用户当前审计 checkout，不能从技能安装目录推断产品根。

## 范围与提交信息

先看用户指定文件和当前 git status / diff。已有 staged 内容优先复用；若与本次请求不一致，先指出差异。多个不相关改动且范围不明时询问，不全量暂存、不自动 stash 或覆盖用户改动。

按实际变化归纳标题和必要正文。正文优先说明行为、影响及验证，不逐行描述实现。需求关联复用已确认编号，不伪造 tracker；TAPD/GitHub 中单据是否真实存在由相应平台上下文确认，格式校验不负责它。

## 按改动范围选择规则

| 范围 | 标题规则与检查入口 |
| --- | --- |
| 纯前端 | 读取 src/frontend/commitlint.config.js、src/frontend/package.json 与实际安装的 hook；使用前端 commitlint/检查，不要求后端 .venv |
| 后端或混合提交 | 读取 src/backend/docs/pre-commit.md 和 src/backend/.pre-commit-config.yaml；后端标题校验是 agent/backend/tools/commit-message/commit_message.sh，混合任务分别记录前后端覆盖 |
| 根目录或未覆盖的范围 | 以实际 hook、项目规则和用户确认的提交目标为准；不要仅靠目录名猜测适用端 |

当前后端规则限定 type、摘要与末尾 tracker，不接受 Conventional Commits 的 scope 形式；前端 commitlint 支持自己的 type 集合且没有同样的 tracker 必填约束。不能用后端 validator 判定纯前端标题，更不能静默统一配置。package.json 声明 Husky 不等于 hook 已安装；发现 core.hooksPath 与 pre-commit 冲突时报告来源，不自动修改。

需要后端校验时，从产品仓库根调用：

```bash
sh agent/backend/tools/commit-message/commit_message.sh validate --message-file <message-file>
```

需要按 type、summary、tracker 及可选正文条目生成完整 message 时，可用 `agent/backend/tools/commit-message/commit_message.py render`，由后端项目虚拟环境执行；生成结果仍交由同目录 shell 校验。已有 message 的校验和历史检查直接使用 shell。不要为前端安装它，也不要复制正则到本技能。检查历史必须限定用户要求的范围，不把 check-log/check-range 当作普通提交必经步骤。

前端若已具备本地 commitlint，可在前端目录按现有配置检查 message；缺少依赖时如实报告，不擅自安装，也不将跳过检查称为通过。带 --fix 的 lint 会修改文件，使用前确认它属于当前任务范围。

## 用户要求实际提交时

只暂存本次授权文件；按实际端运行所需检查，重新复核工具修改后的 diff，再使用检查通过的 message 提交。后端使用项目 .venv 的 pre-commit，前端使用本端环境；不跳过 hook，不全量暂存，不修改全局 Git 配置或给另一端安装 hook。

仅要求生成 message 时，只返回可使用的信息，不暂存或提交。实际提交后报告 commit、范围与验证；推送、改写已共享历史、PR/MR 和部署不由提交请求自动授权。
