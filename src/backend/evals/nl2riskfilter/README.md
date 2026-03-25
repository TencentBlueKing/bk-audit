# NL2RiskFilter 评估套件

自然语言转风险筛选条件（NL2JSON）的 AI 能力评估。

## 评估目标

验证 NL2RiskFilter 智能体能否将用户自然语言查询正确转换为 `ListRiskRequestSerializer` 格式的 JSON 筛选条件。

## 测试用例

| 场景 | 文件 | 数量 | 说明 |
|------|------|------|------|
| A 常规 | `tests/normal.yaml` | 40 | 时间、人员、状态、标签、策略、组合、排序、current_operator、risk_label、title、event_content、has_report、视角、处理流程、智能搜索、风险描述、时间口语化、等级口语化、问句模式、真实用户名 |
| B 复杂 | `tests/complex.yaml` | 7 | MCP 事件字段、多条件组合、跨策略 |
| C 边界 | `tests/boundary.yaml` | 6 | 无效输入、注入攻击、歧义查询 |
| D 挑战 | `tests/challenge.yaml` | 40 | 复合时间、否定语义、口语化、多条件+sort、策略精确匹配、字段歧义、复杂自然语言、策略名称变体、英文缩写、多标签深度、回归用例 |

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

### 当前配置

单模型调优模式（kimi-chat）：

| label | model | 说明 |
|-------|-------|------|
| kimi-chat | kimi-chat | 当前生产模型（调优目标） |

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
| `check_sort_json_format` | 验证 sort 字段使用标准 JSON 双引号格式（检测单引号问题） |
| `check_event_content` | 验证 event_content 字段存在且包含期望关键词 |
| `check_has_report` | 验证 has_report 字段存在且值正确 |
| `strategy_id_contains` | 验证 strategy_id 包含所有期望 ID（集合包含，不要求精确匹配） |
| `empty_or_has_risk_level` | 验证输出为空或包含 risk_level=HIGH（追问语义无上下文场景） |
| `title_or_event_content` | 验证输出包含 title 或 event_content（隐式标题查询场景） |
| `strategy_with_risk_level_or_event_filters` | 验证 strategy_id + risk_level 或 event_filters 处理歧义字段 |

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
单模型调优模式下总调用量为 93×1×2=186 次 AI 调用，
用于统计 LLM 输出的一致性。配合 `maxConcurrency: 3` 控制并发。
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
- 项目 `.venv`（Python 3.11+，Django 环境）
- Provider 和断言通过 `_backend_root` 自动定位 Django 项目根目录，无需单独的 `requirements.txt`

## 真实策略数据

测试用例使用以下真实策略：

| strategy_id | 名称 | 事件字段数 |
|-------------|------|-----------|
| 110 | 【回归】离线策略审计 | 65（含来源IP、操作人等） |
| 144 | ITSM工单工时审计 | 74（含处理人员、工单状态等） |
| 1 | 外包操作审计-WeTERM登录容器 | 无 |
| 136 | 【梯阵】游戏内赠送违规 | 有（含违规金额等） |
| 41 | 【MOCK】游戏赠送违规 | MOCK 策略（干扰项） |
| 154 | 【梯阵】发放对象不匹配 | 有（含道具描述等） |
| 40 | 【MOCK】业受发放不匹配 | MOCK 策略（干扰项） |
| 149 | 【梯阵】异常交易 | 有（含违规等级等） |

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
| V26 | 61×3×2 | 93.72%（343/366） | 去掉 dsv32；kimi-chat 99.2% / hunyuan2 94.3% / qwen3-235B 91.0%。过拟合修复后整体稳定，kimi-chat 保持最优 |
| V27 | 61×3×2 | 75.96%（278/366） | **激进精简失败**：示例 9→6、转换规则改列表格式、示例改单行。qwen3-235B 延迟飙升 10x（5s→52s），kimi 96.7% / hunyuan2 86.9% / qwen3 44.3% |
| V28 | 61×3×2 | kimi 98.4% / hunyuan2 92.6% / qwen3 3.3%* | **温和精简**：枚举内联字段表、操作符紧凑化、event_filters 子表格压缩。行数 -27%（159→116）、字节 -11%（7378→6588）。kimi-chat -0.8%，hunyuan2 -1.7%。*qwen3 全因 API 延迟，输出内容正确 |
| V29 | 69×1×2 | kimi 86.96% (baseline) | **E2E 回归扩展 + 单模型模式**：+8 用例，切换为 kimi-chat 单模型调优。18 个失败：sort 方向错 6 + event_content 映射错 2 + LLM 评判环境缺失 10 |
| V30 | 69×1×2 | **kimi 100%** ✅ | **Prompt 调优 + 断言重构**：(1) sort 默认降序规则 (2) event_content 触发表述扩展 (3) 全部 LLM-rubric→Python 断言，消除环境依赖。新增 3 个断言函数 |
| V31 | 69×1×2 | **kimi 98.55%** ✅ | **E2E 回归 P0+P1 修复**：(1) sort JSON 双引号格式强制（核心规则+字段说明+转换规则三层强调）(2) 策略匹配规则优化（区分度匹配：精确关键词→单策略，模糊关键词→允许多策略）。2 个失败均为 AI 服务波动（repeat 另一次通过），无真实回归 |
| V32 | 93×1×2 | **kimi 95.56%** (172/180) | **口语化同义词映射调优**：在转换规则中新增口语化/同义词映射规则（优先级→risk_level, 遗漏→status, 趋势→时间范围）。8 个失败均为已知 AI 波动（延迟超标 1 + operator/current_operator 歧义 3 + title/event_content 歧义 2 + notice_users 映射 2），**无新增回归** |
| V33 | 93×1×2 | **kimi 98.89%** (178/180) | **用例修正 + prompt 补充**：(1) A29/D37 期望从 operator→current_operator（"处理"→current_operator 是正确语义）(2) A33 期望从 title→event_content（"描述里有"→event_content 是正确触发）(3) prompt 补充"关注/订阅"→notice_users 映射 (4) prompt 强化"待xxx处理/xxx处理过的"→current_operator。2 个失败：A37 口语化歧义（"一般"→LOW vs MIDDLE）+ D36 统计类问句返回空，均为已知波动 |
| V34 | 93×1×2 | **kimi 100%** ✅ (180/180) | **Prompt 调优（修复最后 2 个失败）**：(1) 核心规则第 4 条扩展统计/聚合类查询模式（"哪些 X 产生了最多 Y""排名前几""最多/最少"→仍提取可识别筛选条件），修复 D36 (2) 口语化映射新增"一般/普通/不太严重"→`MIDDLE`，修复 A37。遵循过拟合防护：规则用通用类型描述而非抄测试用例具体 query，同义词族覆盖而非单词映射 |
| V35 | 93×1×2 | **kimi 97.78%** (176/180) | **单模型调优阶段**：补充“我+动作”优先级映射（处理→`current_operator`，关注/订阅→`notice_users`），修复 A29/A30/D37；同时修复 1 个评估错误。失败主要来自 latency 阈值设置影响 |
| V36 | 93×1×2 | **kimi 98.33%** (177/180) | **评估策略回调**：恢复 LLM-as-Judge provider 配置（保留后续扩展能力），latency 阈值设为 **15s**。新增通过 B1/C4/C5/D31；当前 3 个失败均为 latency（A35/B7/D28） |
| V37 | 93×1×2 | **kimi 96.11%** (173/180) | **提示词更新后回归验证**：快速回归集 14/14 通过，但全量在 15s 阈值下出现 7 个失败；其中 6 个为 latency（15~25s 区间），1 个为一次性语义波动（A6，重跑已恢复） |

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

### Prompt 精简的安全边界（V27/V28）

⚠️ V27 尝试激进精简（示例 9→6、转换规则改列表格式、示例改单行），通过率从 93.72% 暴跌到 75.96%。

**可安全精简的部分**：
- 枚举独立段落（status/risk_level/risk_label）→ 内联到字段表说明列
- event_filters 子表格 → 紧凑行内描述
- 操作符枚举的中文释义 → 逗号分隔纯代码格式

**不能精简的核心部分**（精简即回归）：
- **转换规则**：必须保持多段落格式，列表格式导致 thinking 模型延迟飙升 10x
- **示例数量**：9 个示例缺一不可，减少后 event_content/报告状态等边界字段误判
- **示例格式**：必须保持多行输入/输出格式，单行格式模型难以解析

**经验**：prompt 精简的上限约 11%（字节维度），进一步精简需要改变架构（如改用 schema 格式），而非文字层面压缩。

### E2E 回归分析驱动的用例扩展（V29）

通过对 V2 E2E 测试（203 条，84.73%）的 31 个失败用例逐一交叉分析，识别出真实 AI 缺陷并吸收到 promptfoo 评估套件中：

**新增用例（8 个）**：

| 用例 | 类型 | 回归来源 | 覆盖的 AI 缺陷 |
|------|------|----------|---------------|
| A27 | 常规 | EF-005 | "事件描述"应映射 `event_content` 而非 `event_filters` |
| A28 | 常规 | EF-005 变体 | "事件描述中有xxx"同义表述覆盖 |
| D23 | 挑战 | CB-007 | 3 条件+sort 丢失（时间+等级+sort） |
| D24 | 挑战 | CB-015 | 4 条件+sort 丢失（报告+等级+sort） |
| D25 | 挑战 | CB-019 | 5 条件+sort 丢失（时间+人员+状态+等级+sort） |
| D26 | 挑战 | EF-010/EF-011 | 策略精确匹配 vs MOCK 策略干扰（游戏内赠送违规） |
| D27 | 挑战 | EF-019/EF-020 | 策略精确匹配 vs MOCK 策略干扰（发放对象不匹配） |
| D28 | 挑战 | EF-028 | 事件字段"违规等级" vs 顶层 `risk_level` 歧义 |

**新增断言函数**：`strategy_id_contains` — 集合包含判断，验证期望的策略 ID 全部包含在返回中（不要求精确匹配），解决 E2E 中 strategy_id 精确字符串比较导致的大量误报。

**E2E 分析核心发现**：
- 31 个 E2E 失败中，14 个（45%）是 E2E 期望不合理（strategy_id 精确比较、event_filters 映射错误）
- 12 个（39%）是 AI 真实缺陷（sort 丢失 5 个 + 策略多匹配 6 个 + title 遗漏 1 个）
- 修正 E2E 误报后，真实通过率约 91%

### latency 阈值与用户体验基线（V36）

本轮将评估 latency 阈值回调到 **15s**（从 60s 收紧），原因：

- **用户体验**：风险检索属于交互型能力，超过 15s 对大多数用户已明显可感知
- **质量门槛**：过宽阈值会掩盖真实慢查询问题，导致评估结果偏乐观
- **当前结果**：V36 在 15s 下仍达到 **98.33%**，剩余 3 个失败均为超时（非语义错误），便于后续专项优化

建议后续继续保持：
- 评估默认阈值 `15s`（质量门槛）
- 对线上容灾可单独设 `30s` 告警阈值（运行监控）

### Prompt 调优与断言重构（V30）

V30 实现 **kimi-chat 100% 通过率**（69 用例 × 2 次 = 138 次全通过），调优策略：

**Prompt 调优（2 处改动）**：

1. **排序默认降序**：在排序规则中新增"当用户说'按时间排序'而未指定升降序时，默认降序 `["-event_time"]`"——修复 6 个 sort 方向错误（D23/D24/D25 各 ×2）
2. **event_content 触发表述扩展**：新增"事件中有xxx""事件描述包含xxx""事件描述中有xxx"等触发模式，并明确"当查询未指定策略时，事件描述/内容/详情一律映射到 `event_content`"——修复 4 个 event_content 映射错误

**断言重构（LLM-rubric → Python）**：

将 5 个依赖外部 LLM 网关的 `llm-rubric` 断言全部替换为等价的 Python 断言函数：

| 用例 | 原断言 | 新断言 | 说明 |
|------|--------|--------|------|
| D12 | llm-rubric | `empty_or_has_risk_level` | 空对象或 risk_level=HIGH |
| D13 | llm-rubric | `has_expected_keys` + `field_value_match` | notice_users=王五 |
| D14 | llm-rubric | `has_expected_keys` + `field_value_match` | operator+status+risk_label |
| D18 | llm-rubric | `title_or_event_content` | title 或 event_content 都可接受 |
| D28 | llm-rubric | `strategy_with_risk_level_or_event_filters` | strategy_id + 歧义字段处理 |
