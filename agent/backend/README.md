# 后端能力

## 工程来源

| 任务 | 来源 |
| --- | --- |
| 开发环境与项目结构 | [后端 README](../../src/backend/README.md) |
| 单元测试与运行资源 | [测试指南](../../src/backend/docs/testing.md) |
| 格式、hook 与提交标题 | [pre-commit 指南](../../src/backend/docs/pre-commit.md)与[实际配置](../../src/backend/.pre-commit-config.yaml) |

## 领域技能

| 技能 | 用途 |
| --- | --- |
| [adding-iam-resource-type](skills/adding-iam-resource-type/SKILL.md) | IAM 类型、provider、迁移与资产同步 |
| [ai-eval-suite](skills/ai-eval-suite/SKILL.md) | 评测集、运行、失败分析、调优与重评估 |

## 后端工具

[shell 校验器](tools/commit-message/commit_message.sh)提供标题校验、hook 和历史检查，是后端标题规则来源。[可选消息生成器](tools/commit-message/commit_message.py)按 type、summary、tracker 和正文条目生成完整提交信息，再调用同目录 shell 校验；hook 和 CI 不依赖该 Python 入口。后端 Python 使用项目虚拟环境，运行测试前按工程来源隔离测试库、队列和 Redis。
