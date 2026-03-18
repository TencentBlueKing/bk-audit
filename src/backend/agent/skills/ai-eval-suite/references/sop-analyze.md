# SOP 3: 分析评估结果

## 分析入口

评估完成后，有两种分析方式：

### 方式 1: 交互式报告（快速浏览）

```bash
npx promptfoo view
```

适合快速定位哪些用例失败、查看具体的输入输出和断言失败原因。

### 方式 2: 解析 output JSON（深度分析）

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

## 分析报告模板

分析完成后，向用户呈现结构化的报告：

```
## 评估结果摘要

- 总用例数: XX
- 通过: XX (XX%)
- 失败: XX
- 错误: XX
- 目标阈值: XX%

## 失败用例分析

### 字段缺失 (N 个)
| 用例 | 缺少字段 | 可能原因 |
|------|---------|---------|
| ... | ... | ... |

### 值错误 (N 个)
| 用例 | 字段 | 期望值 | 实际值 | 可能原因 |
|------|------|-------|-------|---------|
| ... | ... | ... | ... | ... |

## 根因总结

1. [最主要的问题]
2. [次要问题]

## 建议调优方向

→ 进入 SOP 4（调优）
```

## 使用分析脚本

本 skill 内置了 `scripts/analyze_results.py`，可以自动解析 promptfoo 输出 JSON 并生成
结构化的失败分析报告。

```bash
# 单次分析
python <skill-path>/scripts/analyze_results.py evals/<suite>/output/results.json

# 两轮对比（调优前 vs 调优后）
python <skill-path>/scripts/analyze_results.py before.json after.json

# 输出到文件
python <skill-path>/scripts/analyze_results.py results.json -o report.md
```

脚本会自动：
- 兼容 promptfoo 不同版本的 JSON 输出格式（`results.results` 和 `results.table.body`）
- 按失败类型分类（空输出、格式错误、字段缺失、值错误、语义不符、超时、网络错误等）
- 生成对比报告（新增通过、新增失败/回归、持续失败）

如果脚本的分类不够精确，可以在脚本输出的基础上进一步人工分析。

## 分析原则

1. **先看全局再看细节** — 先统计各类失败的数量分布，再逐个分析
2. **找系统性问题** — 如果多个用例因相同原因失败，说明是系统性问题（如枚举缺失）
3. **区分模型问题和测试问题** — 有时是期望值不合理，而非模型输出错误
4. **关注 error vs failure** — error 是基础设施问题，failure 是能力问题，处理方式不同

---

→ 分析完成后，进入 **SOP 4（调优）**：读 `sop-tune.md`
