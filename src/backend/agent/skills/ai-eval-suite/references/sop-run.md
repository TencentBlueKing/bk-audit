# SOP 2: 运行评估

## 子 agent 调用

评估运行耗时长（几十秒到几分钟）、无需交互，**强烈推荐**交给子 agent 执行。

**子 agent prompt 模板**（直接复制使用）：

> 在 `{project_root}` 执行评估命令并报告结果。
>
> **运行命令**：
> ```
> cd {project_root} && PROMPTFOO_PYTHON=$(pwd)/.venv/bin/python npx promptfoo eval -c {config_path} --env-file .env --no-cache -o {output_path}
> ```
>
> 运行完成后报告：1) 终端输出的通过率摘要 2) 失败用例数 3) 耗时。
> 如果命令报错，报告完整错误信息。

## 两种运行模式

### 模式 A: 快速验证（调试阶段）

改了 prompt/代码后快速确认修改生效，**不用于出结论**。

```bash
cd <project-root>
PROMPTFOO_PYTHON=$(pwd)/.venv/bin/python \
npx promptfoo eval -c evals/<suite>/promptfooconfig.yaml \
  --env-file .env --no-cache \
  --filter-providers <单模型label> --filter-first-n 10
```

- 可用 `--filter-providers` 只跑单模型
- 可用 `--filter-first-n` / `--filter-pattern` / `--filter-failing` 缩小范围
- **不带 `-o`**，避免产出不完整的归档文件

### 模式 B: 正式评估（出结论 / 归档）

⚠️ **必须覆盖 config 中所有 provider，禁止 `--filter-providers`。** 带 `-o` 导出完整结果。

```bash
cd <project-root>
PROMPTFOO_PYTHON=$(pwd)/.venv/bin/python \
npx promptfoo eval -c evals/<suite>/promptfooconfig.yaml \
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
| `--filter-providers <label>` | 只跑指定模型 | **仅 A** |
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
| npx 下载失败（内网） | `npm install -g promptfoo` 后直接用 `promptfoo` 命令 |
| LLM-as-Judge 404 | 确认 `defaultTest.options.provider` 配置正确 |
| Django provider 初始化失败 | 确保 `DJANGO_SETTINGS_MODULE` 已设置、cwd 在项目根 |

---

→ 评估完成。下一步分析结果：
```bash
python <skill-path>/scripts/analyze_results.py <结果文件.json>
```
→ 读 `sop-analyze.md`
