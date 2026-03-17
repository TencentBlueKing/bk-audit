# 项目结构与配置模板

## 目录约定

### 多 Suite 并存结构

```
<project-root>/
├── evals/                         # 评估根目录
│   ├── README.md                  # 统筹入口：整体说明、已有 suite 列表
│   ├── .gitignore                 # 忽略 output 目录
│   │
│   ├── providers/                 # 公共 provider（跨 suite 复用）
│   │   └── bk_llm_provider.py    # 蓝鲸 LLM 网关（可选，LLM-as-Judge 用）
│   │
│   ├── <suite-a>/                 # 评估套件 A
│   │   ├── promptfooconfig.yaml   # 主配置
│   │   ├── README.md              # suite 详细说明
│   │   ├── providers/             # 业务专用 provider
│   │   │   └── provider.py
│   │   ├── assertions/            # 自定义断言（如需要）
│   │   │   └── check_output.py
│   │   ├── tests/
│   │   │   ├── normal.yaml
│   │   │   ├── complex.yaml
│   │   │   └── boundary.yaml
│   │   └── output/                # 评估结果（git 忽略）
│   │       └── .gitkeep
│   │
│   └── <suite-b>/                 # 评估套件 B
│       └── ...
│
└── .env                           # 环境变量（git 忽略）
```

**两层 provider 体系**：
- `evals/providers/` — 公共 provider，各 suite 通过 `python:../providers/xxx.py` 引用
- `evals/<suite>/providers/` — 业务专用 provider，走完整业务链路

### 命名规范

| 元素 | 规范 | 示例 |
|------|------|------|
| Suite 目录名 | 小写，连字符或下划线 | `text2sql`、`intent-classify` |
| 配置文件 | 固定 `promptfooconfig.yaml` | - |
| Provider 文件 | `provider.py`（单 provider 时） | 多 provider 时用描述性名称 |
| 断言文件 | 按功能命名 | `check_filters.py`、`check_format.py` |
| 测试文件 | 按场景命名 | `normal.yaml`、`complex.yaml` |
| 输出文件 | 日期前缀 + 描述 | `20260316-results.json`、`20260317-fix-enum.json` |

### .gitignore 模板

```gitignore
*/output/*.json
*/output/*.html
*/output/*.csv
*/output/*.md
__pycache__/
*.pyc
node_modules/
*.local
```

## promptfooconfig.yaml 模板

### 模板 A: 基础（自定义 Provider）

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
    - type: python
      value: 'file://assertions/check_output.py:basic_validation'

tests:
  - file://tests/normal.yaml
  - file://tests/complex.yaml
  - file://tests/boundary.yaml
```

### 模板 B: 多模型对比

```yaml
# yaml-language-server: $schema=https://promptfoo.dev/config-schema.json
description: '<能力名称> 多模型对比'

prompts:
  - file://prompts/chat.json

providers:
  - id: openai:chat:gpt-4.1-mini
    label: 'GPT-4.1-mini'
    config:
      temperature: 0
  - id: anthropic:messages:claude-sonnet-4-6
    label: 'Claude Sonnet'
    config:
      temperature: 0

defaultTest:
  assert:
    - type: cost
      threshold: 0.05
    - type: latency
      threshold: 10000

tests: file://tests/*.yaml
```

### 模板 C: 带稳定性测试 + LLM-as-Judge

```yaml
# yaml-language-server: $schema=https://promptfoo.dev/config-schema.json
description: '<能力名称> 稳定性测试（多模型对比 + 模型辅助断言）'

prompts:
  - '{{query}}'

providers:
  - id: 'python:providers/provider.py'
    label: '<model-a>'
    config:
      model: '<model-a>'
  - id: 'python:providers/provider.py'
    label: '<model-b>'
    config:
      model: '<model-b>'

evaluateOptions:
  maxConcurrency: 3
  repeat: 2
  delay: 500

# grader provider 用于 llm-rubric 等模型辅助断言
defaultTest:
  options:
    provider:
      id: 'python:../providers/bk_llm_provider.py'
      config:
        model: '<grader-model>'
  assert:
    - type: python
      value: 'file://assertions/check_output.py:basic_validation'
    - type: latency
      threshold: 30000

tests:
  - file://tests/normal.yaml
  - file://tests/complex.yaml
  - file://tests/boundary.yaml
  - file://tests/challenge.yaml
```

## evals/README.md 模板

```markdown
# AI 能力评估体系

基于 [promptfoo](https://promptfoo.dev) 的自动化评估框架。

## 目录约定

\`\`\`
evals/
├── providers/                  # 公共 provider（跨评测套件复用）
│   └── bk_llm_provider.py     # 蓝鲸 LLM 网关（LLM-as-Judge 用）
│
├── <suite-a>/                  # 评估套件 A
│   ├── promptfooconfig.yaml
│   ├── providers/              # 业务专用 provider
│   ├── assertions/             # 自定义断言
│   ├── tests/                  # 测试用例
│   └── output/                 # 评估结果（.gitignore）
│
└── <suite-b>/                  # 评估套件 B
    └── ...
\`\`\`

## 已有评估项目

| 项目 | 用例数 | 说明 |
|------|--------|------|
| `<suite-a>/` | XX | 描述 |

## 快速开始

### 环境准备

\`\`\`bash
# 确保 .env 中配置了必要的环境变量（AI 服务地址、LLM 网关等）
# Python provider 依赖项目虚拟环境
export PROMPTFOO_PYTHON=$(pwd)/.venv/bin/python
\`\`\`

### 运行评估

\`\`\`bash
cd <project-root>
npx promptfoo eval -c evals/<suite>/promptfooconfig.yaml \
  --env-file .env --no-cache
\`\`\`

## 新建评估项目

参考 `ai-eval-suite` skill 的 SOP 1（初始化 Suite）。
```

## Suite README 模板

```markdown
# <能力名称> 评估套件

<一句话描述>

## 评估目标

验证 <能力名称> 能否 <做什么>。

## 测试用例

| 场景 | 文件 | 数量 | 说明 |
|------|------|------|------|
| 常规 | `tests/normal.yaml` | X | ... |
| 复杂 | `tests/complex.yaml` | X | ... |
| 边界 | `tests/boundary.yaml` | X | ... |

## Provider 说明

- **业务 provider** (`providers/provider.py`): 调用 <业务接口>，走完整链路
- **Grader provider** (`../providers/bk_llm_provider.py`): 蓝鲸 LLM 网关，用于 llm-rubric 断言

## 运行

\`\`\`bash
cd <project-root>
npx promptfoo eval -c evals/<suite>/promptfooconfig.yaml \
  --env-file .env --no-cache \
  -o evals/<suite>/output/$(date +%Y%m%d)-results.json
\`\`\`

## 环境依赖

- `.env` 中需配置 AI 服务地址、LLM 网关地址等（详见项目 .env.example）

## 通过率阈值

目标：>= XX%

## 评估迭代进展

| 版本 | 日期 | 用例数 | 通过率 | 关键变化 |
|------|------|--------|--------|---------|
| V1   | YYYY-MM-DD | X | XX% | 初始版本 |
```
