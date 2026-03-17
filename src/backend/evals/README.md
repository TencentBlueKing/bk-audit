# AI 能力评估体系

基于 [promptfoo](https://promptfoo.dev) 的自动化评估框架，用于对比不同模型、提示词、MCP 配置下各 AI 能力的表现，反向驱动优化。

## 目录约定

```
evals/
├── README.md
├── .gitignore
├── providers/                  # 公共 provider（跨评测套件复用）
│   └── bk_llm_provider.py     # 蓝鲸 LLM 网关（OpenAI 标准协议）
│
├── nl2riskfilter/              # NL2RiskFilter 评估项目
│   ├── promptfooconfig.yaml    # 评估配置
│   ├── providers/              # 业务专用 provider
│   ├── assertions/             # 自定义断言
│   ├── tests/                  # 测试用例（按场景分文件）
│   └── output/                 # 评估结果（.gitignore）
│
└── <其他AI能力>/               # 未来扩展
    └── ...
```

- `evals/providers/` — 公共 provider，各评测套件通过 `python:../providers/xxx.py` 引用
- `evals/<能力>/providers/` — 业务专用 provider，走完整业务链路

## 快速开始

### 环境准备

```bash
# 设置评估用户（必须，无默认值）
export BKAPP_EVAL_USERNAME=your_rtx

# 确保 .env 中配置了以下环境变量：
# BKAPP_AI_RISK_SEARCH_API_URL — AI 风险检索服务地址
# BKAPP_LLM_GW_ENDPOINT       — LLM 网关地址（LLM-as-Judge 用）

# Python provider 依赖项目的 Django 环境（.venv），无需单独的 requirements.txt
# 确保已激活项目虚拟环境，或设置 PROMPTFOO_PYTHON 指向项目 Python
export PROMPTFOO_PYTHON=$(pwd)/.venv/bin/python
```

### 运行评估

```bash
cd src/backend

# 运行评估（--env-file 加载 .env 中的 AI 服务地址等配置）
npx promptfoo eval -c evals/nl2riskfilter/promptfooconfig.yaml \
  --env-file .env --no-cache

# 导出结果到 JSON（带日期，便于对比回归）
npx promptfoo eval -c evals/nl2riskfilter/promptfooconfig.yaml \
  --env-file .env --no-cache \
  -o evals/nl2riskfilter/output/$(date +%Y%m%d)-results.json

# 查看交互式报告
npx promptfoo view
```

### 验证配置

```bash
npx promptfoo validate -c evals/nl2riskfilter/promptfooconfig.yaml
```

## 新建评估项目

1. 创建 `evals/<能力名>/` 目录，包含 `providers/`、`assertions/`、`tests/`、`output/`
2. 编写 `promptfooconfig.yaml`（参考 `nl2riskfilter/` 示例）
   - 顶部加 `# yaml-language-server: $schema=https://promptfoo.dev/config-schema.json`
   - 字段顺序：description → prompts → providers → defaultTest → tests
3. 编写 provider（直调业务接口，走完整链路）
4. 编写断言（确定性断言优先，模型辅助断言慎用）
5. 编写测试用例（覆盖 happy path / edge case / regression / security）
6. 运行验证

## SOP：评估闭环流程

```
构建评测集 → 评估 → 分析报告 → 调优 → 重评估 → 达标
```

1. **构建评测集**：从业务场景出发，按维度组织测试用例
2. **运行评估**：`npx promptfoo eval -c <config> --no-cache`
3. **分析报告**：`npx promptfoo view` 查看交互式报告，聚焦失败用例
4. **调优**：根据失败分析调整 prompt / 模型配置 / MCP 工具
5. **重评估**：回到步骤 2，直到达标
6. **归档**：导出结果，记录调优决策

## 断言优先级

```
确定性断言（快、免费、稳定）  →  优先使用
    ↓ 不够用时
相似度断言（较快、便宜）
    ↓ 仍不够用时
模型辅助断言（慢、花钱、有波动）  →  慎用
```

## 已有评估项目

| 项目 | 用例数 | 说明 |
|------|--------|------|
| `nl2riskfilter/` | 45 | 自然语言转风险筛选条件（NL2JSON） |
