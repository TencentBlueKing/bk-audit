# NL2RiskFilter 评估套件

自然语言转风险筛选条件（NL2JSON）的 AI 能力评估。

## 评估目标

验证 NL2RiskFilter 智能体能否将用户自然语言查询正确转换为 `ListRiskRequestSerializer` 格式的 JSON 筛选条件。

## 测试用例

| 场景 | 文件 | 数量 | 说明 |
|------|------|------|------|
| A 常规 | `tests/normal.yaml` | 26 | 时间、人员、状态、标签、策略、组合、排序、current_operator、risk_label、title、event_content、has_report |
| B 复杂 | `tests/complex.yaml` | 7 | MCP 事件字段、多条件组合、跨策略 |
| C 边界 | `tests/boundary.yaml` | 6 | 无效输入、注入攻击、歧义查询 |
| D 挑战 | `tests/challenge.yaml` | 22 | 复合时间、否定语义、口语化、LLM-as-Judge、回归用例 |

## Provider

`providers/provider.py` 直接调用 `NL2RiskFilter().request()`，走完整业务链路：

```
RequestSerializer → perform_request → build_nl2risk_user_message
→ chat_completion → extract_json_from_text → ResponseSerializer
```

### 多模型对比

Provider 支持通过 `config.model` / `config.non_thinking_llm` / `config.system_prompt` 注入参数到 `execute_kwargs`，
在 provider 层 `patch("services.web.risk.resources.risk.api.bk_plugins_ai_agent.chat_completion", wrapped_fn)` 实现，
不修改任何业务代码。

当前配置了三个 provider 并排对比：

| label | model | 说明 |
|-------|-------|------|
| kimi-chat | kimi-chat | 当前生产模型 |
| hunyuan2 | hunyuan2 | 候选模型 |
| qwen3-235B | qwen3-235B | 候选模型 |

## 自定义断言

| 函数 | 说明 |
|------|------|
| `is_non_empty_filter` | 验证返回非空 filter_conditions |
| `has_expected_keys` | 验证包含指定字段 |
| `field_value_match` | 验证字段值精确匹配 |
| `has_event_filter_field` | 验证 event_filters 包含指定事件字段（支持模糊匹配） |
| `passes_serializer_validation` | 通过 ListRiskRequestSerializer 校验（defaultTest） |
| `expect_empty_or_message` | 无效输入应返回空条件 |
| `check_message_on_empty` | 空条件时 message 应非空 |
| `partial_match` | 部分匹配评分（>=50% 通过） |
| `check_time_range` | 验证 start_time/end_time 在合理范围内 |
| `check_sort` | 验证 sort 数组包含期望的排序字段 |
| `check_event_content` | 验证 event_content 字段存在且包含期望关键词 |
| `check_has_report` | 验证 has_report 字段存在且值正确 |

## 运行

```bash
cd src/backend

# 必须设置环境变量
export BKAPP_EVAL_USERNAME=your_rtx

# 运行评估 — 双模型对比（结果输出到 output/ 目录）
npx promptfoo eval -c evals/nl2riskfilter/promptfooconfig.yaml \
  --env-file .env --no-cache \
  -o evals/nl2riskfilter/output/$(date +%Y%m%d)-multimodel.json

# 只跑单个模型（如仅 dsv32）
npx promptfoo eval -c evals/nl2riskfilter/promptfooconfig.yaml \
  --env-file .env --no-cache --filter-providers dsv32

# 快速验证（只跑第 1 个用例）
npx promptfoo eval -c evals/nl2riskfilter/promptfooconfig.yaml \
  --env-file .env --no-cache --filter-first-n 1

# 查看交互式报告
npx promptfoo view
```

## 稳定性设计

配置了 `evaluateOptions.repeat: 2`，每个用例运行 2 次。
三模型对比模式下总调用量为 45×3×2=270 次 AI 调用，
用于统计 LLM 输出的一致性。配合 `maxConcurrency: 3` 和 `delay: 500` 控制并发和限流。
稳定性衡量：2 次运行中任意一次失败即视为不稳定。

## vars 中的 JSON 字符串约定

promptfoo 的 vars 只支持字符串类型。数组和对象需要用 JSON 字符串传递，
在自定义断言中用 `json.loads()` 解析：

```yaml
vars:
  expected_keys: '["risk_level", "start_time"]'     # JSON 数组字符串
  expected_values: '{"risk_level": "HIGH"}'          # JSON 对象字符串
  tags: '[{"id": 1, "name": "数据安全"}]'             # JSON 数组字符串
  strategies: '[]'                                    # 空数组
```

## 环境依赖

- `.env` 中需配置 `BKAPP_AI_RISK_SEARCH_API_URL`（AI 服务地址）
- `BKAPP_EVAL_USERNAME` 环境变量（用于"我的风险"等场景）
- `BKAPP_LLM_GW_ENDPOINT`（LLM-as-Judge 用的 LLM 网关地址，必填）
- `BKAPP_LLM_APP_CODE` / `BKAPP_LLM_APP_SECRET`（缺省 fallback `BKPAAS_APP_ID` / `BKPAAS_APP_SECRET`）
- 项目 `.venv`（Python 3.11+，Django 环境）
- Provider 和断言通过 `_backend_root` 自动定位 Django 项目根目录，无需单独的 `requirements.txt`

## 真实策略数据

测试用例使用以下真实策略：

| strategy_id | 名称 | 事件字段数 |
|-------------|------|-----------|
| 110 | 【回归】离线策略审计 | 65（含来源IP、操作人等） |
| 144 | ITSM工单工时审计 | 74（含处理人员、工单状态等） |
| 1 | 外包操作审计-WeTERM登录容器 | 无 |

## 评估迭代进展

| 版本 | 用例数 | 通过率 | 说明 |
|------|--------|--------|------|
| V7 | 35 | 100% | 状态枚举修正后最终结果 |
| V8 | 35 | - | 工程化重构（目录通用化） |
| V13 | 35×2 | dsv32 91.4% / qwen3-235B 92.9% | 多模型对比（dsv32 vs qwen3-235B）+ repeat:2 稳定性评测 |
| V14 | 45×2 | 87.8%（158/180） | 阶段 A 完成：评测集扩展到 45 用例，新增断言，暴露隐藏问题 |
| V15 | 45×2 | 91.1%（164/180） | 模型参数一致（model+non_thinking_llm）、system_prompt 动态读取 |
| V16 | 45×2 | 95.6%（172/180） | LLM-as-Judge 直调 LLM 网关（OpenAI 标准协议）、provider 公共化重构 |
| V17 | 45×2 | 96.1%（173/180） | prompt 调优：title 字段 + 统计类查询规则 + 示例补充；D12 用例放宽期望 |
| V18 | 45×3×2 | 96.7%（261/270） | 新增 kimi-chat 模型对比；dsv32 93.3% / qwen3-235B 98.9% / kimi-chat 97.8% |
| V21 | 45×4×2 | 90.56%（326/360） | 新增 hunyuan2；kimi-chat 97.8% / qwen3-235B 96.7% / hunyuan2 84.4% / dsv32 83.3% |
| V23 | 61×4×2 | 93.65% 加权（kimi 99.2% / hunyuan2 95.1% / qwen3 92.6% / dsv32 87.7%） | 回归驱动扩展：+16 用例覆盖 event_content/has_report/title 变体；断言模糊匹配；prompt 调优；latency 阈值 30s→60s。hunyuan2 +10.7%，dsv32 +4.4% |
| V24 | 61×4×2 | 待评估 | 过拟合修复：示例去重（6/9 示例与测试用例重复→0/9）；转换规则抽象化（枚举具体模式→概括性描述）；示例值差异化（不同措辞/值/等级） |

## 评估反馈与经验

评估过程中沉淀的可持久化经验，供后续迭代参考。

### Prompt 修改必须同步 generate.py

⚠️ `services/web/ai/prompts/nl2riskfilter/system_prompt.md` 是由 `generate.py` 动态生成的产物。

**正确流程**：修改 prompt → 先改 `generate.py` → 运行生成脚本 → 验证产物一致

```bash
# 重新生成 system_prompt.md
python -m services.web.ai.prompts.nl2riskfilter.generate

# 确认生成结果与预期一致
git diff services/web/ai/prompts/nl2riskfilter/system_prompt.md
```

**反面案例**（V23 教训）：直接修改 `system_prompt.md` 但未同步 `generate.py`，导致下次生成会覆盖手动改动。后续补救同步了 `generate.py`，新增了标题("关于xxx")、`event_content`、`has_report` 三条转换规则和示例 7-9。

### 过拟合检测与修复（V24）

⚠️ V23 存在中等偏严重的过拟合风险，按 `ai-eval-suite` 的 SOP 4 检查清单发现：

**问题**：
- 9 个 prompt 示例中有 5 个与测试用例完全一致（示例 4/5/7/8/9），1 个高度相似（示例 1）
- 转换规则枚举了测试用例中的具体表述模式，而非概括性描述
- 部分通过率提升来自"记忆"而非"理解"

**修复措施**：
1. **示例去重**：所有示例的具体措辞/值/等级与测试用例差异化（如"我的风险"→"我负责处理的风险"，"标签为重要"→"紧急标签"，"sudo"→"root操作"）
2. **规则抽象化**：title/event_content/has_report 三条规则从枚举具体模式改为概括性描述（如"当用户意图是按事件文本内容搜索时→event_content"）
3. **示例值差异化**：示例 1 从"最近一周高风险"改为"最近一个月中等风险"，示例 9 从"高危"改为"中等"

**验证标准**：V24 评估中，如果通过率**小幅下降（≤3%）**是预期内的健康信号——说明之前的部分通过率确实靠"记忆"支撑；如果**大幅下降（>5%）**则需进一步分析规则是否过度抽象。
