# SOP 2: 运行评估

## 子 agent 调用

评估运行可异步执行并检查；子 agent 仅在环境支持且当前任务允许时使用。

先复用项目已安装或锁定的 promptfoo。以下 npx 示例仅用于已有可用依赖的环境；缺少依赖时先确认安装方式，不自动下载或全局安装。

## 两种运行模式

### 模式 A: 快速验证（调试阶段）

改了 prompt/代码后快速确认修改生效，**不用于出结论**。

```bash
cd <project-root>
PROMPTFOO_PYTHON=$(pwd)/.venv/bin/python \
npx promptfoo eval --no-table -c evals/<suite>/promptfooconfig.yaml \
  --env-file .env --no-cache \
  --filter-providers <单模型label> --filter-first-n 10
```

- 可用 `--filter-providers` 只跑单模型
- 可用 `--filter-first-n` / `--filter-pattern` / `--filter-failing` 缩小范围
- **不带 `-o`**，避免产出不完整的归档文件

### 模式 B: 正式评估（出结论 / 归档）

覆盖已确认的用例和 provider 范围，带 `-o` 导出结果。用户指定局部评估时保留该范围，不擅自扩展；报告注明过滤条件，不把局部结果称为全配置通过。

```bash
cd <project-root>
PROMPTFOO_PYTHON=$(pwd)/.venv/bin/python \
npx promptfoo eval --no-table -c evals/<suite>/promptfooconfig.yaml \
  --env-file .env --no-cache \
  -o evals/<suite>/output/$(date +%Y%m%d)-vN-results.json
```

文件名可带调优描述便于回溯：`$(date +%Y%m%d)-v7-fix-enum.json`

### 成本估算

```
调用次数 = provider 数 × 用例数 × repeat
示例：4 × 45 × 2 = 360 次/轮
```

调试阶段用模式 A 控制规模，正式评估再跑全量。

### 运行前检查

正式评估前确认：
- [ ] prompt 由生成脚本产出 → 是否已重新运行生成脚本？
- [ ] 修改了 provider 代码 → 是否需要重启服务？
- [ ] 修改了测试用例 → `npx promptfoo validate` 是否通过？

## 命令参数速查

| 参数 | 作用 | 模式 |
|------|------|------|
| `-c <config>` | 指定配置文件 | A/B |
| `--env-file .env` | 加载环境变量 | A/B |
| `--no-cache` | 禁用缓存 | A/B |
| `-o <path>` | 导出结果 | **仅 B** |
| `--filter-providers <label>` | 只跑指定模型，报告中注明范围 | A/B |
| `--filter-first-n N` | 只跑前 N 个用例 | A |
| `--filter-pattern <regex>` | 按描述过滤用例 | A |
| `--filter-failing <path>` | 只重跑上次失败 | A |
| `--repeat N` | 重复运行 N 次 | A/B |
| `--max-concurrency N` | 最大并发（默认 4） | A/B |

## 输出格式

| 格式 | 扩展名 | 适用场景 |
|------|--------|---------|
| JSON | `.json` | 分析脚本、CI/CD（**默认选择**） |
| HTML | `.html` | 可视化报告、团队分享 |
| CSV | `.csv` | Excel 分析 |

多格式同时导出：`-o evals/<suite>/output/结果文件.json -o evals/<suite>/output/结果文件.html`

## 运行完成后

终端摘要：`Results: ✓ 30 passed, ✗ 5 failed, 0 errors (85.7%)`

交互式报告（多 provider 横向对比最直观）：`npx promptfoo view`

## 常见问题

| 问题 | 排查 |
|------|------|
| AI 服务连接失败 | 检查 `.env` 地址、`--env-file .env` 是否添加 |
| `-o` 写入位置不对 | 路径相对于 cwd（始终在项目根目录运行） |
| 缓存导致结果不更新 | `npx promptfoo cache clear` |
| Python 版本不匹配 | `export PROMPTFOO_PYTHON=$(pwd)/.venv/bin/python` |
| promptfoo 不可用或下载失败 | 核对项目已有版本与依赖来源；确需安装时先确认，不自动改全局环境 |
| LLM-as-Judge 404 | 确认 `defaultTest.options.provider` 配置正确 |
| Django provider 初始化失败 | 确保 `DJANGO_SETTINGS_MODULE` 已设置、cwd 在项目根 |

---

仅要求运行评估时，报告执行范围、结果文件和摘要后结束。请求包含结果分析时再读 `sop-analyze.md`，使用项目虚拟环境执行分析脚本。
