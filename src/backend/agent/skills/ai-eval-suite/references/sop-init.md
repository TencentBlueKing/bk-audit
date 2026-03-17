# SOP 1: 初始化评估套件

## 流程概览

```
询问评估目标 → 创建目录结构 → 编写 provider → 编写测试用例 → 编写配置 → validate
```

## Step 1: 询问评估目标

向用户收集以下信息（保持简单，不问多余的）：

1. **评估什么 AI 能力？**
   - 名称会作为目录名（如 `text2sql`、`intent_classify`）
   - 一句话描述能力的输入和输出

2. **输入是什么？**
   - 自然语言查询
   - 结构化数据（JSON / 表单）
   - 多轮对话

3. **输出是什么？**
   - JSON 结构（最常见，需要字段级验证）
   - 自由文本（需要语义级验证）
   - 分类标签（需要精确匹配）

4. **"好"的标准是什么？**
   - 精确匹配特定字段值
   - 包含关键信息
   - 通过业务 Serializer 校验
   - 语义正确（需要模型辅助断言）

5. **通过率阈值？**
   - 建议默认 90%，用户可调整
   - 记录到 suite 的 README 中

## Step 2: 创建目录结构

在项目的 `evals/` 目录下创建：

```
evals/<suite-name>/
├── promptfooconfig.yaml      # 主配置
├── README.md                 # suite 说明文档
├── providers/
│   └── provider.py           # 自定义 provider
├── assertions/               # 自定义断言（如需要）
│   └── check_output.py
├── tests/
│   ├── normal.yaml           # 常规场景
│   ├── complex.yaml          # 复杂场景
│   ├── boundary.yaml         # 边界场景
│   └── challenge.yaml        # 挑战场景（可选）
└── output/                   # 评估结果（git 忽略）
    └── .gitkeep
```

确保 `evals/.gitignore` 包含 `*/output/*.json` 和 `*/output/*.md`。

## Step 3: 编写 Provider

Provider 的职责是调用真实的业务接口，返回 promptfoo 期望的格式。

**provider.py 基本结构：**

```python
import json
import os
import sys
import time

def call_api(prompt, options, context):
    """promptfoo 调用入口"""
    vars_ = context.get("vars", {})
    config = options.get("config", {})

    # 1. 从 vars 和 config 中提取参数
    query = vars_.get("query", prompt)

    # 2. 调用业务接口
    start = time.time()
    try:
        result = call_your_business_api(query)
    except Exception as exc:
        return {"error": f"调用失败: {exc}"}
    latency_ms = round((time.time() - start) * 1000)

    # 3. 返回标准格式
    return {
        "output": json.dumps(result, ensure_ascii=False),
        "metadata": {
            "latency_ms": latency_ms,
            "raw_result": result,
        },
    }
```

**关键原则：**
- 直接调用业务接口，走完整链路，不要简化或跳过步骤
- 环境变量不允许敏感默认值，缺失时返回明确错误
- 返回的 `output` 是字符串，`metadata` 用于断言中访问额外信息

## Step 4: 编写测试用例

按场景维度组织，每个文件覆盖一类场景：

| 文件 | 覆盖范围 | 示例 |
|------|---------|------|
| `normal.yaml` | 用户最常见的查询 | 单条件筛选、简单组合 |
| `complex.yaml` | 多条件组合、跨模块 | 多字段联合、嵌套条件 |
| `boundary.yaml` | 边界和异常输入 | 空输入、注入攻击、歧义 |
| `challenge.yaml` | 挑战模型能力极限 | 否定语义、口语化、复合条件 |

**单个测试用例结构：**

```yaml
- description: '简短描述这个用例测什么'
  vars:
    query: '用户输入'
    # 其他变量...
    expected_keys: '["field1", "field2"]'
    expected_values: '{"field1": "value1"}'
  assert:
    - type: python
      value: 'file://assertions/check_output.py:has_expected_keys'
    - type: python
      value: 'file://assertions/check_output.py:field_value_match'
```

**用例设计原则：**
- 每个用例有明确的 `description`
- `vars` 中包含输入和期望值
- 断言从确定性开始，不够用时才加模型辅助
- 覆盖 happy path / edge case / regression / security

## Step 5: 编写配置

**promptfooconfig.yaml 模板：**

```yaml
# yaml-language-server: $schema=https://promptfoo.dev/config-schema.json
description: '<能力名称> AI 能力评估'

prompts:
  - '{{query}}'

providers:
  - id: 'python:providers/provider.py'
    label: '<能力名称>-Real'
    config:
      username: '{{env.EVAL_USERNAME}}'

defaultTest:
  vars:
    username: '{{env.EVAL_USERNAME}}'
  assert:
    - type: python
      value: 'file://assertions/check_output.py:basic_validation'

tests:
  - file://tests/normal.yaml
  - file://tests/complex.yaml
  - file://tests/boundary.yaml
```

**字段顺序规范：** description → prompts → providers → defaultTest → evaluateOptions → tests

## Step 6: 验证

```bash
cd <project-root>

# 验证配置语法
npx promptfoo validate -c evals/<suite>/promptfooconfig.yaml

# 快速测试一个用例
npx promptfoo eval -c evals/<suite>/promptfooconfig.yaml \
  --env-file .env --no-cache --filter-first-n 1
```

## Step 7: 编写 Suite README

每个 suite 维护独立的 README.md，包含：
- 评估目标
- 测试用例概览（场景、数量）
- Provider 说明
- 自定义断言说明
- 运行命令
- 环境依赖
- 通过率阈值
