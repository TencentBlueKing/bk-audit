# SOP 2: 运行评估

## 标准运行命令

```bash
cd <project-root>

# 基本运行
npx promptfoo eval -c evals/<suite>/promptfooconfig.yaml \
  --env-file .env --no-cache

# 带日期归档的运行（推荐）
npx promptfoo eval -c evals/<suite>/promptfooconfig.yaml \
  --env-file .env --no-cache \
  -o evals/<suite>/output/$(date +%Y%m%d)-results.json
```

## 命令参数说明

| 参数 | 作用 | 是否必须 |
|------|------|---------|
| `-c <config>` | 指定配置文件路径 | 必须 |
| `--env-file .env` | 加载环境变量（AI 服务地址等） | 必须 |
| `--no-cache` | 禁用缓存，确保每次真实调用 | 开发阶段必须 |
| `-o <path>` | 导出结果到文件 | 需要归档或分析时 |
| `--filter-first-n N` | 只运行前 N 个用例 | 调试时用 |
| `--filter-pattern <regex>` | 按描述过滤用例 | 只跑特定用例时 |

## 输出格式选择

| 格式 | 扩展名 | 适用场景 |
|------|--------|---------|
| JSON | `.json` | 程序分析、AI 解析、CI/CD |
| HTML | `.html` | 可视化报告、团队分享 |
| CSV | `.csv` | Excel 分析 |

```bash
# 同时导出多种格式
npx promptfoo eval -c evals/<suite>/promptfooconfig.yaml \
  --env-file .env --no-cache \
  -o evals/<suite>/output/$(date +%Y%m%d)-results.json \
  -o evals/<suite>/output/$(date +%Y%m%d)-report.html
```

## 运行后输出摘要

运行完成后，promptfoo 会在终端输出摘要表格。关注以下信息：

```
Results: ✓ 30 passed, ✗ 5 failed, 0 errors (85.7%)
Duration: 45s (concurrency: 4)
```

- **passed**: 所有断言通过的用例数
- **failed**: 至少一个断言失败的用例数
- **errors**: provider 调用出错的用例数（区别于断言失败）
- **Duration**: 总耗时

## 查看交互式报告

```bash
npx promptfoo view
```

在浏览器中打开交互式报告，可以：
- 逐个查看每个用例的输入、输出、断言结果
- 按通过/失败筛选
- 查看详细的断言失败原因

## 常见问题

### AI 服务连接失败

如果看到 provider error（如"AI 服务暂时不可用"），检查：
1. AI 服务是否已启动
2. `.env` 中的服务地址是否正确
3. `--env-file .env` 是否已添加

### 结果写入位置不对

`-o` 参数的路径是相对于运行命令的 cwd，不是配置文件目录。
始终在项目根目录运行，用完整相对路径指定输出位置。

### 缓存导致结果不更新

开发阶段务必加 `--no-cache`。如果怀疑缓存问题：
```bash
npx promptfoo cache clear
```
