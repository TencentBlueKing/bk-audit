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
| `--filter-failing <path>` | 只重跑上次失败的用例 | 调优后快速验证 |
| `--repeat N` | 每个用例重复运行 N 次 | 评估输出稳定性 |
| `--max-concurrency N` | 最大并发数（默认 4） | 大量用例时调整 |

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

## 运行环境常见坑

### Python 版本不匹配

promptfoo 默认使用系统 Python 执行 `python:` provider。如果项目使用虚拟环境中的
特定 Python 版本（如 3.11），而系统 Python 是 3.10，可能出现 `ImportError`
（如 `cannot import name 'Self' from 'typing'`）。

**解决方案**：通过 `PROMPTFOO_PYTHON` 环境变量指定 Python 路径：

```bash
export PROMPTFOO_PYTHON=$(pwd)/.venv/bin/python
```

或在运行命令前激活虚拟环境，并确保 `PATH` 中虚拟环境的 Python 优先：

```bash
source .venv/bin/activate
export PATH="$(pwd)/.venv/bin:$PATH"
```

### npx promptfoo 下载失败

在内网环境或使用 npm 镜像时，`npx promptfoo` 可能因 403/网络错误无法下载。

**解决方案**：
1. 全局安装：`npm install -g promptfoo`，然后直接使用 `promptfoo` 命令
2. 检查 npm 镜像配置：`npm config get registry`
3. 如果之前成功运行过，npx 会缓存二进制文件，可以直接找到缓存路径执行

### LLM-as-Judge 404 / 鉴权失败

使用 `llm-rubric` 等模型辅助断言时，如果 grader provider 配置不正确会出现 404 或鉴权错误。

**排查步骤**：
1. 确认 `defaultTest.options.provider` 已正确配置（不要依赖 promptfoo 默认的 OpenAI key）
2. 检查 `.env` 中 LLM 网关地址和鉴权信息是否完整
3. 用 curl 单独测试 LLM 网关连通性
4. 确认 provider 路径的相对位置正确（`python:../providers/xxx.py` 是相对于 config 文件）

### Django provider 初始化失败

如果业务 provider 依赖 Django 环境，确保：
1. `DJANGO_SETTINGS_MODULE` 环境变量已设置
2. provider 文件中正确设置了 `sys.path` 和 `django.setup()`
3. 运行目录（cwd）是项目根目录，否则 Django 可能找不到配置文件

---

→ 评估运行完成后，进入 **SOP 3（分析评估）**：读 `sop-analyze.md`
