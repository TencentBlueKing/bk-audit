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
│   │   │   ├── <场景a>.yaml
│   │   │   ├── <场景b>.yaml
│   │   │   └── ...              # 按业务场景拆分
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

### 公共资源扩展（多 suite 共享）

当公共资源不止 provider 时（如共享 defaultTest、assertions、tests），可以参考
[promptfoo 官方推荐](https://www.promptfoo.dev/docs/configuration/modular-configs/)
升级为统一的公共目录：

```
evals/
├── shared/                        # 公共资源（目录名自定义，官方常用 configs/ 或 shared/）
│   ├── providers/                 # 公共 provider
│   │   └── bk_llm_provider.py
│   ├── defaultTest.yaml           # 共享的默认断言（cost / latency / 安全检查等）
│   └── assertions/                # 共享的自定义断言
│       └── common.py
├── <suite-a>/
│   └── promptfooconfig.yaml       # 引用：providers: file://../shared/providers.yaml
└── <suite-b>/
    └── promptfooconfig.yaml
```

各 suite 通过 `file://` 相对路径引用公共资源：

```yaml
providers: file://../shared/providers.yaml
defaultTest: file://../shared/defaultTest.yaml
```

当前只有公共 provider 时，`evals/providers/` 已经够用，无需提前改造。
当共享资源增多到 2-3 类时再考虑升级。

### 命名规范

| 元素 | 规范 | 示例 |
|------|------|------|
| Suite 目录名 | 小写，连字符或下划线 | `text2sql`、`intent-classify` |
| 配置文件 | 固定 `promptfooconfig.yaml` | - |
| Provider 文件 | `provider.py`（单 provider 时） | 多 provider 时用描述性名称 |
| 断言文件 | 按功能命名 | `check_filters.py`、`check_format.py` |
| 测试文件 | 按业务场景命名 | `single-filter.yaml`、`edge-case.yaml` |
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
    - type: is-json

tests:  # 文件名按 SOP 1 Step 5 与用户讨论确定
  - file://tests/<场景a>.yaml
  - file://tests/<场景b>.yaml
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
      id: 'python:../providers/<grader-provider>.py'  # 蓝鲸项目用 bk_llm_provider.py
      config:
        model: '<grader-model>'
  assert:
    - type: python
      value: 'file://assertions/check_output.py:basic_validation'
    - type: latency
      threshold: 30000

tests:  # 文件名按 SOP 1 Step 5 与用户讨论确定
  - file://tests/<场景a>.yaml
  - file://tests/<场景b>.yaml
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
| <场景a> | `tests/<场景a>.yaml` | X | ... |
| <场景b> | `tests/<场景b>.yaml` | X | ... |

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

## 调优上下文（推荐，首次调优时填写）

后续迭代调优时会反复用到的背景信息，首次调优时记录一次，避免每轮重新收集。

### Prompt 管理

- **Prompt 位置**：<文件路径 或 第三方平台>
- **修改方式**：<直接编辑 / 修改生成脚本后重新生成 / 在平台上更新>
- **生成脚本**（如有）：<路径，如 `services/web/ai/prompts/xxx/generate.py`>

### MCP / 工具链

- **MCP 工具列表**：<工具名称和用途>
- **数据源**：<工具返回的数据从哪来、覆盖哪些字段>
- **已知限制**：<工具返回数据的已知缺陷或不完整之处>

### 调优经验沉淀

记录历次调优中发现的有效手段和踩坑经验，供后续迭代参考：

| 手段 | 效果 | 备注 |
|------|------|------|
| <如：增加枚举映射表> | <如：枚举类失败全部修复> | <适用场景> |

## 评估迭代进展

| 版本 | 日期 | 用例数 | 通过率 | 关键变化 |
|------|------|--------|--------|---------|
| V1   | YYYY-MM-DD | X | XX% | 初始版本 |
```
