# 前端能力

| 任务 | 工程来源 |
| --- | --- |
| 构建与检查命令 | [package.json](../../src/frontend/package.json) |
| 脚本与组件风格 | [ESLint](../../src/frontend/.eslintrc.js) |
| 样式规范 | [Stylelint](../../src/frontend/stylelint.config.js) |
| 类型检查 | [TypeScript](../../src/frontend/tsconfig.json)与 package.json 的 `type-check` |
| 提交标题 | [commitlint](../../src/frontend/commitlint.config.js)与实际 hook |

`lint-script`、`lint-style` 包含 `--fix`，执行前确认当前请求允许文件修改。前端使用自己的依赖、配置和提交门禁。
