# 发布前自检清单

在将评估套件交付或集成到 CI/CD 之前，对照以下清单检查。

## 配置文件

- [ ] 顶部有 `# yaml-language-server: $schema=https://promptfoo.dev/config-schema.json`
- [ ] 有 `description` 字段，3-10 个词描述评估目的
- [ ] 字段顺序：description → prompts → providers → defaultTest → evaluateOptions → tests
- [ ] 环境变量用 `'{{env.VAR}}'` 语法（不是 `$VAR`）
- [ ] 无敏感信息硬编码（用户名、密钥、内网域名等）
- [ ] 没有使用 `outputPath`（改用 CLI `-o` 参数）

## Provider

- [ ] 业务 provider 调用真实业务接口，走完整链路
- [ ] 无 mock provider
- [ ] 环境变量缺失时返回明确错误信息
- [ ] 返回格式正确：`{"output": "...", "metadata": {...}}`
- [ ] 公共 provider 放在 `evals/providers/`，业务 provider 放在 `evals/<suite>/providers/`

## 断言

- [ ] `defaultTest` 设置了通用断言（如格式校验）
- [ ] 确定性断言优先，模型辅助断言只在必要时使用
- [ ] 使用模型辅助断言时，`defaultTest.options.provider` 已指定 grader provider
- [ ] 自定义断言函数返回 `{"pass": bool, "score": float, "reason": str}`

## 测试用例

- [ ] 每个用例有明确的 `description`
- [ ] 覆盖维度：常规 / 复杂 / 边界 / 挑战
- [ ] 覆盖类型：happy path / edge case / regression / security
- [ ] 期望值合理，与业务逻辑一致

## 目录结构

- [ ] 遵循 `evals/<suite>/` 目录约定
- [ ] 公共 provider 在 `evals/providers/`（如有）
- [ ] 有 `output/` 目录和 `.gitkeep`
- [ ] `evals/.gitignore` 包含 `*/output/*.json` 等规则
- [ ] 有 suite 级 README.md

## 运行环境

- [ ] `PROMPTFOO_PYTHON` 指向项目虚拟环境的 Python（如需要）
- [ ] `npx promptfoo validate -c <config>` 通过
- [ ] `--no-cache` 运行一次确认结果符合预期
- [ ] `--env-file .env` 能正确加载环境变量
- [ ] `-o` 输出到正确位置
- [ ] LLM-as-Judge grader 连通性已验证（如使用模型辅助断言）

## 文档

- [ ] Suite README 包含：评估目标、用例概览、Provider 说明、运行命令、环境依赖、通过率阈值
- [ ] Suite README 包含评估迭代进展表
- [ ] evals/README.md 已更新 suite 列表和目录约定
