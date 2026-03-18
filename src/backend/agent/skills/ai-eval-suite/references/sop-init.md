# SOP 1: 初始化评估套件

## 目录

- [流程概览](#流程概览)
- [Step 1: 询问评估目标](#step-1-询问评估目标)
- [Step 2: 创建目录结构](#step-2-创建目录结构)
- [Step 3: 引入公共 Provider](#step-3-引入公共-provider)
- [Step 4: 编写业务 Provider](#step-4-编写业务-provider)
- [Step 5: 编写测试用例](#step-5-编写测试用例)
- [Step 6: 编写自定义断言（可选）](#step-6-编写自定义断言可选)
- [Step 7: 编写配置](#step-7-编写配置)
- [Step 8: 验证](#step-8-验证)
- [Step 9: 编写 Suite README](#step-9-编写-suite-readme)

## 流程概览

```
询问评估目标 → 创建目录结构 → 引入公共 provider → 编写业务 provider
→ 编写测试用例 → 编写断言（可选）→ 编写配置 → validate → 编写 Suite README
```

## Step 1: 询问评估目标

向用户收集以下信息（保持简单，不问多余的）：

1. **评估什么 AI 能力？**
   - 名称会作为目录名（如 `text2sql`、`intent-classify`）
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

6. **是否需要模型辅助断言（llm-rubric 等）？**
   - 如果需要，确认 LLM 网关地址和鉴权方式
   - 蓝鲸项目可直接使用内置的 `bk_llm_provider.py`

## Step 2: 创建目录结构

在项目的 `evals/` 目录下创建：

```
evals/
├── providers/                    # 公共 provider（首次创建时建立）
│   └── bk_llm_provider.py       # LLM 网关（可选，蓝鲸项目用）
│
└── <suite-name>/
    ├── promptfooconfig.yaml      # 主配置
    ├── README.md                 # suite 说明文档
    ├── providers/
    │   └── provider.py           # 业务专用 provider
    ├── assertions/               # 自定义断言（可选，按需创建）
    │   └── check_output.py      # 仅在内置断言不够用时编写
    ├── tests/
    │   ├── normal.yaml           # 常规场景
    │   ├── complex.yaml          # 复杂场景
    │   ├── boundary.yaml         # 边界场景
    │   └── challenge.yaml        # 挑战场景（可选）
    └── output/                   # 评估结果（git 忽略）
        └── .gitkeep
```

确保 `evals/.gitignore` 包含 `*/output/*.json` 和 `*/output/*.md`。

## Step 3: 引入公共 Provider（可选）

如果评估需要模型辅助断言（`llm-rubric`、`factuality` 等），需要一个 grader provider。

**蓝鲸项目**：将本 skill 内置的 `scripts/bk_llm_provider.py` 复制到 `evals/providers/`：

```bash
# 首次创建公共 provider 目录
mkdir -p evals/providers/
# <skill-path> 即本 skill 所在目录，例如 agent/skills/ai-eval-suite
cp <skill-path>/scripts/bk_llm_provider.py evals/providers/
```

然后在 `.env` 中配置：

```bash
# LLM 网关（LLM-as-Judge 用）
BKAPP_LLM_GW_ENDPOINT=<你的 LLM 网关地址>
BKAPP_LLM_APP_CODE=<应用 code>
BKAPP_LLM_APP_SECRET=<应用 secret>
```

**非蓝鲸项目**：根据实际 LLM 接口编写自己的 grader provider，或直接使用 promptfoo 内置的
`openai:chat:xxx`（需配置 `OPENAI_API_KEY`）。

## Step 4: 编写业务 Provider

Provider 的职责是调用真实的业务接口，返回 promptfoo 期望的格式。

如果你的 AI 能力就是直接调用 LLM（而非经过业务接口封装），可以跳过此步骤，
直接在 `promptfooconfig.yaml` 中引用公共 provider（如 `python:../providers/bk_llm_provider.py`）。

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

## Step 5: 编写测试用例

按场景维度组织，每个文件覆盖一类场景：

| 文件 | 覆盖范围 | 示例 |
|------|---------|------|
| `normal.yaml` | 用户最常见的查询 | 单条件筛选、简单组合 |
| `complex.yaml` | 多条件组合、跨模块 | 多字段联合、嵌套条件 |
| `boundary.yaml` | 边界和异常输入 | 空输入、注入攻击、歧义 |
| `challenge.yaml` | 挑战模型能力极限 | 否定语义、口语化、复合条件 |

**单个测试用例结构（使用内置断言，推荐快速上手）：**

```yaml
- description: '简短描述这个用例测什么'
  vars:
    query: '用户输入'
  assert:
    - type: is-json
    - type: javascript
      value: 'JSON.parse(output).field_name !== undefined'
    - type: contains
      value: '"expected_value"'
```

**使用自定义断言（复杂校验场景）：**

```yaml
- description: '需要复杂校验的用例'
  vars:
    query: '用户输入'
    expected_keys: '["field1", "field2"]'
    expected_values: '{"field1": "value1"}'
  assert:
    - type: python
      value: 'file://assertions/check_output.py:has_expected_keys'
    - type: python
      value: 'file://assertions/check_output.py:field_value_match'
```

**⚠️ javascript 断言必须写成单行**：promptfoo 的 `javascript` 断言需要表达式的最终值作为返回值。
不要使用 YAML 多行格式（`|` 或 `>`），否则 promptfoo 无法获取返回值，会报
`Custom function must return a boolean, number, or GradingResult object` 错误。
多条语句用分号连接写在一行内：

```yaml
# ✅ 正确：单行，分号连接
- type: javascript
  value: 'const d = JSON.parse(output); d.intent === "query" && d.confidence >= 0.5'

# ❌ 错误：YAML 多行格式，promptfoo 无法获取返回值
- type: javascript
  value: |
    const d = JSON.parse(output);
    d.intent === "query" && d.confidence >= 0.5
```

**用例设计原则：**
- 每个用例有明确的 `description`
- `vars` 中包含输入和期望值
- 断言从确定性开始，不够用时才加模型辅助
- 覆盖 happy path / edge case / regression / security

## Step 6: 编写自定义断言（可选）

如果内置断言（`is-json`、`contains`、`javascript`、`regex` 等）不够用，
可以编写 Python 自定义断言函数。

**assertions/check_output.py 基本结构：**

```python
import json

def get_assert(output, context):
    """基础校验：输出是合法 JSON 且非空"""
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return {"pass": False, "score": 0, "reason": "输出不是合法 JSON"}
    if not data:
        return {"pass": False, "score": 0, "reason": "输出为空"}
    return {"pass": True, "score": 1, "reason": "基础校验通过"}

def has_expected_keys(output, context):
    """检查输出 JSON 是否包含期望的字段"""
    expected = json.loads(context["vars"].get("expected_keys", "[]"))
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return {"pass": False, "score": 0, "reason": "输出不是合法 JSON"}
    missing = [k for k in expected if k not in data]
    if missing:
        return {"pass": False, "score": 0, "reason": f"缺少字段: {missing}"}
    return {"pass": True, "score": 1, "reason": "所有期望字段都存在"}
```

**自定义断言函数规范：**
- 函数签名：`def func_name(output, context)` — output 是字符串，context 包含 vars
- 返回格式：`{"pass": bool, "score": float, "reason": str}`
- 在 yaml 中引用：`file://assertions/check_output.py:func_name`

如果不需要自定义断言，可以跳过此步骤，`assertions/` 目录也无需创建。

## Step 7: 编写配置

配置模板见 `references/project-structure.md` 中的"模板 A / B / C"，根据场景选择：

| 模板 | 适用场景 |
|------|---------|
| 模板 A | 基础评估（单模型 + 确定性断言） |
| 模板 B | 多模型对比 |
| 模板 C | 带稳定性测试 + LLM-as-Judge |

**最小可用配置（模板 A 简化版）：**

```yaml
# yaml-language-server: $schema=https://promptfoo.dev/config-schema.json
description: '<能力名称> AI 能力评估'

prompts:
  - '{{query}}'

providers:
  - id: 'python:providers/provider.py'
    label: '<model-name>'
    config:
      model: '<model-name>'

defaultTest:
  assert:
    - type: is-json

tests:
  - file://tests/normal.yaml
  - file://tests/complex.yaml
  - file://tests/boundary.yaml
```

如果需要 `llm-rubric` 等模型辅助断言，在 `defaultTest` 中增加 `options.provider`：

```yaml
defaultTest:
  options:
    provider:
      id: 'python:../providers/bk_llm_provider.py'
      config:
        model: '<grader-model-name>'
```

**字段顺序规范：** description → prompts → providers → defaultTest → evaluateOptions → tests

## Step 8: 验证

```bash
cd <project-root>

# 确保 promptfoo 使用项目 Python 环境
export PROMPTFOO_PYTHON=$(pwd)/.venv/bin/python

# 验证配置语法
npx promptfoo validate config -c evals/<suite>/promptfooconfig.yaml

# 快速测试一个用例
npx promptfoo eval -c evals/<suite>/promptfooconfig.yaml \
  --env-file .env --no-cache --filter-first-n 1
```

## Step 9: 编写 Suite README

每个 suite 维护独立的 README.md，模板见 `references/project-structure.md` 的"Suite README 模板"。

README 应包含：评估目标、测试用例概览、Provider 说明、运行命令、环境依赖、通过率阈值、
评估迭代进展表，以及可选的"调优上下文"（Prompt 位置、MCP 工具链、调优经验沉淀）：

```markdown
## 评估迭代进展

| 版本 | 日期 | 用例数 | 通过率 | 关键变化 |
|------|------|--------|--------|---------|
| V1   | YYYY-MM-DD | XX | XX% | 初始版本 |
```

每次评估后更新此表（详见 SOP 5 重评估）。这张表是团队了解评估演进历史的核心入口。

---

→ 初始化完成后，进入 **SOP 2（运行评估）**：读 `sop-run.md`
