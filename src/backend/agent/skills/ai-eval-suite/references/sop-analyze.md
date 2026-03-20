# SOP 3: 分析评估结果

## 子 agent 调用

分析脚本执行是机械操作，推荐交给子 agent。根因分析建议主 agent 审阅。

**子 agent prompt 模板**：

> 在 `{project_root}` 执行分析脚本并返回完整输出。
>
> ```
> cd {project_root} && python {skill_path}/scripts/analyze_results.py {result_json} [-o {report_path}]
> ```
>
> 如果结果包含多个 provider，追加 `--by-provider` 生成横向对比表。
> 如果需要对比上一轮，传两个文件：`{before_json} {after_json}`。
> 将脚本的完整输出返回。

## 分析入口

优先使用内置分析脚本，辅以交互式报告做深度检查。

### 内置分析脚本（默认方式）

```bash
# 单次分析
python <skill-path>/scripts/analyze_results.py evals/<suite>/output/结果文件.json

# 多 provider 横向对比（按模型维度拆分通过率、独有失败、延迟）
python <skill-path>/scripts/analyze_results.py evals/<suite>/output/结果文件.json --by-provider

# 两轮纵向对比（调优前 vs 调优后）
python <skill-path>/scripts/analyze_results.py evals/<suite>/output/before.json evals/<suite>/output/after.json

# 输出到文件
python <skill-path>/scripts/analyze_results.py evals/<suite>/output/结果文件.json -o evals/<suite>/output/report.md
```

> `<skill-path>` 即本 skill 加载时输出的 base 目录路径。

脚本能力：
- 兼容 promptfoo 两种 JSON 格式（`results.results` / `results.table.body`）
- 按失败类型分类 + 对比报告（新增通过/失败/回归/持续失败）
- `--by-provider` 模式输出多模型横向对比表

### 解析 output JSON（深度分析）

读取 `-o` 导出的 JSON 文件，提取结构化的失败信息。

**JSON 结构中的关键字段：**

promptfoo 输出有两种格式，分析脚本已兼容两者。

**格式 1: results 列表（常见于 `promptfoo eval -o`）**

```json
{
  "results": {
    "stats": {
      "successes": 30, "failures": 5, "errors": 0,
      "tokenUsage": { "total": 12345 }
    },
    "results": [
      {
        "success": false,
        "testCase": { "description": "用例描述", "vars": { "query": "..." } },
        "response": { "output": "模型输出", "error": null },
        "gradingResult": {
          "componentResults": [
            { "pass": false, "reason": "失败原因", "assertion": { "type": "python" } }
          ]
        }
      }
    ]
  }
}
```

**格式 2: table body（部分版本）**

```json
{
  "results": {
    "stats": { "successes": 30, "failures": 5 },
    "table": {
      "body": [
        {
          "description": "用例描述",
          "vars": { "query": "..." },
          "outputs": [
            { "pass": false, "text": "模型输出", "gradingResult": { "componentResults": [...] } }
          ]
        }
      ]
    }
  }
}
```

**注意**：格式 1 中用例描述在 `row.testCase.description`（不是 `row.description`），
输出在 `row.response.output`，通过状态在 `row.success`。

## 失败分类框架

将失败用例按以下类型分类，有助于定位根因：

### 类型 1: 字段缺失

**特征：** `has_expected_keys` 或 `is-json` schema 断言失败

**典型原因：**
- Prompt 未明确要求输出该字段
- 模型认为该字段不适用于当前查询
- 字段名拼写不一致

**分析方法：** 对比期望字段和实际输出字段，看缺少了哪些

### 类型 2: 值错误

**特征：** `field_value_match` 或 `equals` 断言失败

**典型原因：**
- 枚举映射不正确（如状态码、级别名称）
- Prompt 中的枚举说明不完整或有歧义
- 模型使用了同义词而非精确值

**分析方法：** 对比期望值和实际值，看是否存在系统性偏差

### 类型 3: 格式错误

**特征：** `is-json` / serializer 校验失败

**典型原因：**
- 模型输出被 markdown 代码块包裹
- JSON 中包含注释或尾逗号
- 字段类型不匹配（字符串 vs 数字）

**分析方法：** 查看原始输出文本，确认格式问题的具体表现

### 类型 4: 空输出

**特征：** `is_non_empty` 断言失败，output 为空

**典型原因：**
- 模型未理解查询意图
- Provider 调用出错但未正确传递错误
- 查询超出模型能力范围

**分析方法：** 检查 metadata 中的 message 和 raw_result

### 类型 5: 语义不符

**特征：** `llm-rubric`、`factuality`、`answer-relevance` 等模型辅助断言失败

**典型原因：**
- 模型输出在语义上不符合期望（但格式和字段可能正确）
- 模型对特定场景的理解与期望不一致
- llm-rubric 的评判标准过于严格或模糊

**分析方法：** 查看 grader 的评判理由，判断是模型输出问题还是评判标准问题

### 类型 6: 超时/错误

**特征：** provider error，非断言失败

**典型原因：**
- AI 服务不可用或超时
- 网络问题
- 认证失败

**分析方法：** 检查错误信息，确认是基础设施问题还是业务问题

### 类型 7: 波动/不稳定

**特征：** 同一用例多次运行时，时而通过时而失败，无确定性规律

**典型原因：**
- AI 服务本身的输出不稳定（temperature > 0、模型随机性）
- 网络抖动导致偶发超时
- AI 平台负载波动

**判定方法：** 对可疑用例使用 `--repeat` 和 `--filter-pattern` 重跑：

```bash
# 重跑特定用例 3 次，观察一致性
PROMPTFOO_PYTHON=$(pwd)/.venv/bin/python \
npx promptfoo eval -c evals/<suite>/promptfooconfig.yaml \
  --env-file .env --no-cache \
  --filter-pattern '<用例描述正则>' --repeat 3
```

**处理策略：**
- 3 次中 2 次以上通过 → 标记为"波动"，不需要调优，是 AI 服务固有特性
- 3 次中 2 次以上失败 → 标记为"稳定失败"，需要调优
- 在分析报告中明确区分波动失败和稳定失败，避免浪费时间修复非问题

## 分析报告模板

分析完成后，向用户呈现结构化的报告，并持久化到
`evals/<suite>/output/YYYYMMDD-vN-conclusion.md`（与同轮 JSON/HTML 放在一起）。

```markdown
# <suite> 评估结论 — VN (YYYY-MM-DD)

## 总体结果

| 指标 | 值 |
|------|------|
| 用例数 | XX |
| 通过率 | XX% (XX/XX) |
| 目标阈值 | XX% |
| 是否达标 | ✅ / ❌ |

## 失败分类汇总

按失败类型分类（参考上方"失败分类框架"），列出数量和占比。

## 失败用例分析

按类型逐个列出失败用例、具体表现和可能原因。

## 与上轮对比（V2+ 时填写）

| 维度 | 上轮 | 本轮 | 变化 |
|------|------|------|------|
| 通过率 | XX% | XX% | +X% |
| 新增通过 | — | X 个 | 列出关键用例 |
| 新增失败 | — | X 个 | 列出回归用例 |

## 根因总结

1. [最主要的问题及影响范围]
2. [次要问题]

## 调优建议

- [ ] [建议 1：具体修改方向]
- [ ] [建议 2：具体修改方向]

## 下一步

→ SOP 4 调优 / 已达标，归档
```

**命名约定**：文件名与同轮结果文件对应，如：

```
output/
├── 20260317-v4-results.json
├── 20260317-v4-results.html
└── 20260317-v4-conclusion.md    ← 本轮评估结论
```

## 分析原则

1. **先看全局再看细节** — 先统计各类失败的数量分布，再逐个分析
2. **找系统性问题** — 如果多个用例因相同原因失败，说明是系统性问题（如枚举缺失）
3. **区分模型问题和测试问题** — 有时是期望值不合理，而非模型输出错误
4. **关注 error vs failure** — error 是基础设施问题，failure 是能力问题，处理方式不同
5. **区分波动和稳定失败** — 60%+ 的失败可能是 AI 服务波动，先用 `--repeat` 确认复现性再投入调优

---

→ 分析完成。下一步调优：读 `sop-tune.md`，聚焦根因总结中的 **优先级最高** 问题类型
