# NL2RiskFilter 评估套件

自然语言转风险筛选条件（NL2JSON）的 AI 能力评估。

## 评估目标

验证 NL2RiskFilter 智能体能否将用户自然语言查询正确转换为 `ListRiskRequestSerializer` 格式的 JSON 筛选条件。

## 测试用例

| 场景 | 文件 | 数量 | 说明 |
|------|------|------|------|
| A 常规 | `tests/normal.yaml` | 10 | 时间、人员、状态、标签、策略、组合、排序 |
| B 复杂 | `tests/complex.yaml` | 7 | MCP 事件字段、多条件组合、跨策略 |
| C 边界 | `tests/boundary.yaml` | 6 | 无效输入、注入攻击、歧义查询 |
| D 挑战 | `tests/challenge.yaml` | 12 | 复合时间、否定语义、口语化、多模型对比 |

## Provider

`providers/provider.py` 直接调用 `NL2RiskFilter().request()`，走完整业务链路：

```
RequestSerializer → perform_request → build_nl2risk_user_message
→ chat_completion → extract_json_from_text → ResponseSerializer
```

## 自定义断言

| 函数 | 说明 |
|------|------|
| `is_non_empty_filter` | 验证返回非空 filter_conditions |
| `has_expected_keys` | 验证包含指定字段 |
| `field_value_match` | 验证字段值精确匹配 |
| `has_event_filter_field` | 验证 event_filters 包含指定事件字段 |
| `passes_serializer_validation` | 通过 ListRiskRequestSerializer 校验（defaultTest） |
| `expect_empty_or_message` | 无效输入应返回空条件 |
| `check_message_on_empty` | 空条件时 message 应非空 |
| `partial_match` | 部分匹配评分（>=50% 通过） |

## 运行

```bash
cd src/backend

# 必须设置环境变量
export EVAL_USERNAME=your_rtx

# 运行评估（结果输出到 output/ 目录）
npx promptfoo eval -c evals/nl2riskfilter/promptfooconfig.yaml \
  --env-file .env --no-cache \
  -o evals/nl2riskfilter/output/$(date +%Y%m%d)-results.json

# 查看交互式报告
npx promptfoo view
```

## 稳定性设计

配置了 `evaluateOptions.repeat: 3`，每个用例运行 3 次（35×3=105 次 AI 调用），
用于统计 LLM 输出的一致性。配合 `maxConcurrency: 3` 和 `delay: 500` 控制并发和限流。

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
- `EVAL_USERNAME` 环境变量（用于"我的风险"等场景）
- 项目 `.venv`（Python 3.11+，Django 环境）
- Provider 和断言通过 `_backend_root` 自动定位 Django 项目根目录，无需单独的 `requirements.txt`

## 真实策略数据

测试用例使用以下真实策略：

| strategy_id | 名称 | 事件字段数 |
|-------------|------|-----------|
| 110 | 【回归】离线策略审计 | 65（含来源IP、操作人等） |
| 144 | ITSM工单工时审计 | 74（含处理人员、工单状态等） |
| 1 | 外包操作审计-WeTERM登录容器 | 无 |

## 评估历史

| 版本 | 用例数 | 通过率 | 说明 |
|------|--------|--------|------|
| V7 | 35 | 100% | 状态枚举修正后最终结果 |
| V8 | 35 | - | 工程化重构（目录通用化） |
