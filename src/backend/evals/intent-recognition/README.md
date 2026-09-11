# AI 用户意图判断能力评估套件

验证一期新增的用户意图识别能力：用户自然语言 → 意图分类（选系统 / 日志检索 / 无法识别）+ 目标系统 + AI 动态说明消息。

## 评估目标

`IntentRecognitionService.recognize`（复用生产链路：User Message 模板含 IntentPayload model_json_schema 注入、AIDev Agent 调用、JSON 三级提取闸门、候选白名单校验）能否正确完成：

1. **意图分类**：select_system / log_search / unrecognized 三分类精确匹配
2. **系统路由**：select_system 时 system_id 必须命中候选清单内的目标系统；log_search / unrecognized 时留空
3. **动态消息**：识别成功与无法识别时 message 均为非空的自然语言说明

## 测试用例

| 场景 | 文件 | 数量 | 说明 |
|------|------|------|------|
| 选系统 | `tests/select-system.yaml` | 7 | 场景③系统+检索、场景①纯切系统、命中当前系统、口语变体 |
| 日志检索 | `tests/log-search.yaml` | 4 | 场景②纯检索（不提系统默认当前）、新对话纯检索（识别层判 log_search） |
| 无法识别 | `tests/unrecognized.yaml` | 4 | 闲聊/无关请求 → unrecognized + AI 动态引导 |
| 边界场景 | `tests/edge-cases.yaml` | 5 | 复合意图、近义词、半称、英文、长句多重修饰 |
| 安全 | `tests/safety.yaml` | 4 | 提示注入、候选外系统（越权）、非法结构诱导 |
| 线上事故回归 | `tests/regression-incidents.yaml` | 11 | 2026-09-07 事故：同名/audit 字样干扰消歧、守门不误伤、chain 串联复现 |
| 选系统+多操作人组合 | `tests/chain-scenarios.yaml`（H-J） | 3 | 一句话选系统+多人检索（5 人 include 完整提取）、切换系统+多人+失败、10 人梯度完整性 |

## Provider 说明

- **业务 provider** (`providers/provider.py`): 直接调用 `IntentRecognitionService.recognize`，候选系统为固定合成夹具（审计中心/蓝盾/配置平台/监控平台），`current_system_id` 由测试用例 vars 控制（空 = 新对话）；支持 `config.model` 注入与 `BKAPP_EVAL_USERNAME` 环境变量
- 无模型辅助断言（意图分类为确定性匹配，无需 LLM-as-Judge）

## 运行

```bash
cd src/backend
npx promptfoo eval --no-table -c evals/intent-recognition/promptfooconfig.yaml \
  --env-file .env --no-cache \
  -o evals/intent-recognition/output/$(date +%Y%m%d)-results.json
```

## 环境依赖

- `.env` 中需配置 `BKAPP_EVAL_USERNAME` 与 AIDev 相关环境变量
- Python provider 依赖项目虚拟环境（`PROMPTFOO_PYTHON`）

## 通过率阈值

目标：>= 90%

## 评估迭代进展

| 版本 | 日期 | 用例数 | 通过率 | 关键变化 |
|------|------|--------|--------|---------|
| V1   | 2026-09-06 | 24 | 95.8% | 初始版本，达标（阈值 90%） |
| V2   | 2026-09-06 | 24 | 100% | User Message 模板加半称匹配规则与任务优先声明（不改 System Prompt），V1 失败用例修复且零回归 |
| V3   | 2026-09-06 | 33 | 81.8% | 新增 chain 串联模式 9 用例；6 个失败均为断言路径笔误（condition 项结构为 field 嵌套） |
| V4   | 2026-09-06 | 33 | 100% | 断言路径修正后全量通过：recognize 24 + chain 串联 9 |
| V5   | 2026-09-07 | 41 | 97.6% | 新增线上事故回归 8 用例（candidates: line 线上形态夹具 + chain 守门）；唯一失败为用例断言笔误（守门用例缺 chain: true） |
| V6   | 2026-09-07 | 44 | 100% | 模板消歧调优（见下方调优记录 V2→V6）：同名歧义回归 3 用例 + 全量通过，回归集 repeat5 55/55 稳定 |

### chain 串联模式（V3 起，针对 USER_INTENT 统一入口新设计）

provider 新增 `vars.chain=true` 模式，复刻 `execute_user_intent` 任务的 LLM 编排路径（**两段真实 AIDev 调用**）：

```text
意图识别（recognize）→ 系统路由（select_system 命中 / log_search 复用当前）
  → SYSTEM_REQUIRED 守门形态（新会话纯检索 → error + candidates）
  → 条件识别（NL2JSON + 合成字段上下文，与 audit-log-search 套件同构夹具）
```

建链/复用/续链等确定性 DB 编排由单测覆盖，不进入本层。覆盖的对话场景组合（`tests/chain-scenarios.yaml`）：

| 场景 | 会话状态 | 期望 |
|------|----------|------|
| 系统+日志检索一体（操作人/时间窗） | 新会话 | select_system + system_id + username 条件 + 近 7 天窗口 |
| 系统+日志检索一体（执行结果语义） | 新会话 | result_code 取原始值 -1 |
| 已有系统 + 纯日志检索 | 已选审计中心 | log_search + 复用 system_id + 条件 |
| 已有系统 + 关键词检索 | 已选审计中心 | log 字段 match_any 兜底 |
| 切换系统 + 日志检索 | 已选审计中心→点名蓝盾 | select_system + 新 system_id + 条件 |
| 新会话纯检索 | 无系统 | SYSTEM_REQUIRED + candidates（≥4） |
| 闲聊话语 | 任意 | UNRECOGNIZED_INTENT 结构化协议 |
| 拓展字段下钻 | 已选系统 | extend_data.ticket_id 条件 |
| 纯时间窗口 | 已选系统 | 空 conditions + 默认 30 天窗口 |

### 调优记录（V5 → V6，2026-09-07 线上事故）

**线上事故现象**：
1. 「查询审计中心最近七天的数据」→ 被判 log_search → SYSTEM_REQUIRED 守门（"请先告诉我要查哪个系统的日志..."），点名系统被要求重选
2. 「查询审计中心最近一个月wang的数据」→ system_id 误选 `iam_v4_bk-audit`（scope 显示内部 ID），应为 `bk-audit`（审计中心）

**根因定位（探针实验，repeat 3 × 5 场景）**：
- 线上形态夹具（11 系统 + `iam_v4_bk-audit` 英文名干扰）**不复现**（10/10 正确）
- 30 系统长清单、`审计中心(iam)` 名称变体**均不复现**
- **同名歧义复现**：两候选 name 均为「审计中心」时，「...最近一个月wang的数据」3 轮中 1 轮判 log_search 放弃选择（≈事故 1）；同名 50/50 场景下误选 `iam_v4_bk-audit`（≈事故 2）
- 结论：线上 `iam_v4_bk-audit` 的 name 与「审计中心」相同或高度相似，触发同名歧义

**修复（`intent.py` User Message 模板，不动 System Prompt）**：
1. 匹配优先级分级：name 完全一致 > 简称/部分字模糊 > 英文/ID 形态（中文话语不按英文 ID 字面匹配）
2. 歧义消解三规则：a) name 字面重合度最高优先；b) 中文点名不得仅凭 system_id 含相近英文字样（audit）选择；c) 同名/近名候选优先 system_id 更简洁规范者（`bk-audit` 优于 `iam_v4_bk-audit`）
3. 点名必选：「无法确定具体系统判 log_search」收窄为"无系统指向词或指向词与所有候选均不匹配"；已点名系统名时必须 select_system，不得因存在相似候选放弃选择

**验证**：V6 全量 44/44（100%）；回归集 11 用例 repeat5 = 55/55（0 失败，对比调优前同名场景 1/3 失败率）；单测 8/8 通过

**遗留建议（数据治理，非代码层）**：`iam_v4_*` 前缀为 IAM v4 注册的技术性系统 ID，其 name 与业务系统同名（如「审计中心」）属于候选清单数据质量问题，建议运营侧为这类系统配置可区分的显示名或从检索候选中过滤

### 调优记录（V1 → V2）

- **V1 失败用例**：「看下审计的操作记录」——半称"审计"被保守判为 `log_search`
- **根因**：意图识别 User Message 模板未说明系统名可简称/部分字匹配；复用 agent 的 System Prompt（NL2JSON 条件提取任务）存在轻度干扰
- **修复（`intent.py` 模板，不动 System Prompt——改它影响 NL2JSON 主链路需回归）**：
  1. 任务优先声明：本消息自述完整任务说明，与其他任务指令冲突时以本消息为准（兜底 System Prompt 干扰）
  2. 半称匹配规则：系统名可为全称/简称/部分字（「审计」→「审计中心」），按语义与候选名称/ID 模糊匹配；泛指词（「平台」「系统」）不构成系统指向（防误判）
  3. 防猜选：无法确定具体系统时不要猜选，判 log_search（system_id 留空）
- **验证**：V2 全量重跑 24/24 通过（100%），单测 11 个全过
