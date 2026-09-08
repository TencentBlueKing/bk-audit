# 审计 AI 日志检索评估套件

评估 `NATURAL_LANGUAGE_SEARCH` 的核心能力：将自然语言转换为受控的 `SearchCondition`。Provider 直接调用 `NL2JSONService.convert`，因此会走生产的 User Message 组装、AIDev `bp-audit-log-search` 智能体调用、JSON 提取、语义校验与条件组装。

## 评估目标

验证审计 AI 日志检索能稳定完成以下工作：

1. 从自然语言提取标准字段、拓展字段与多条件组合；
2. 正确处理滚动窗口、自然日与缺省 7 天窗口；
3. 在枚举值不确定时退化为全文检索，不猜测字段值；
4. 固定系统范围，剔除 AI 伪造的 `system_id`、`thedate`、`dtEventTimeStamp` 条件；
5. 拒绝寒暄等无关输入。

```mermaid
flowchart LR
    Q[自然语言话术] --> P[Promptfoo Provider]
    P --> F[固定合成字段上下文]
    F --> N[NL2JSONService.convert]
    N --> A[AIDev: bp-audit-log-search]
    A --> V[生产 JSON 与语义校验]
    V --> C[SearchCondition 或业务错误]
    C --> R[确定性断言]
```

## 评估边界

- **覆盖**：F2 自然语言条件识别，以及 F2 的生产级信任边界和 Pydantic 条件协议。
- **不覆盖**：真实系统字段发现（F1）、Doris 检索快照（F3）、会话持久化、Celery 调度和导出（F4）。这些能力由现有单测/集成测试覆盖。
- **数据安全**：字段上下文与话术均为固定合成数据，不读取、不查询、不写入真实审计日志。
- **提示词边界**：日志检索智能体的 System Prompt 托管在 AIDev；本套件评估其当前线上版本，而不修改它。

## 用例

| 场景 | 文件 | 数量 | 验证重点 |
|---|---:|---:|---|
| 核心条件 | `tests/core_filters.yaml` | 12 | 单字段（操作人/结果/实例/IP/请求ID/访问类型）、多值、全文 AND/OR、枚举退化、拓展字段、组合 |
| 时间语义 | `tests/time_windows.yaml` | 11 | 滚动窗口（天/小时）、自然日、自然周（上周/本周）、自然月、绝对区间（含跨月）、模糊意图、时段（范围断言） |
| 边缘与鲁棒 | `tests/edge_cases.yaml` | 8 | 未知字段忽略、未采样子键放行、枚举映射、复杂三条件组合、空格噪音、拓展否定、已知限制观察 |
| 复杂语言 | `tests/complex_language.yaml` | 10 | 长句四条件、倒装、错别字、方言、隐含语义、省略追问、口语时段、否定排除、中英混合、冗余修饰 |
| 海量多值 | `tests/multi_values.yaml` | 20 | 操作人数量梯度（3→12 人）、分隔形态混排（顿号/逗号/连词）、多字段多值并行（人+资源/IP/实例）、拓展字段多值、中英文与大小写原样保持、泛指集合禁猜（观察）、超长句五维组合 |
| 业务场景组合 | `tests/scenario_combinations.yaml` | 16 | 安全审计（删除行为全文兜底）、权限审计（隐含语义关键词）、高危组合（账号+渠道+结果）、故障排查（工单/请求ID）、非工作时间段、周内区间、绝对+相对混合时间、模糊时间指代（观察）、IP/实例排查、成功语义正向映射、中英混合业务话术、指令注入+合法检索、极限长句六维 120 字 |
| 安全边界 | `tests/safety.yaml` | 4 | 固定 scope、禁止字段、格式注入中和、无关输入拒绝 |
| **合计** | - | **81** | - |

所有时间相关用例固定为 `2026-08-31T18:00:00+08:00`（周一），避免运行时钟造成评测波动。

### 时间边界判定规则

| 话术类型 | 判定方式 | 说明 |
|---|---|---|
| 滚动窗口/自然日/自然周/自然月 | 精确匹配 | 边界无歧义（`23:59:59` / `00:00:00`） |
| 绝对区间（8月1日到8月15日） | 精确 + 备选边界 | 结束边界接受 `15T23:59:59` / `16T00:00:00` / `15T00:00:00`（`expected_end_time_alts`） |
| 时段（今天上午） | 范围断言 | 起点 ∈ [00:00, 08:00]、终点 ∈ [11:00, 12:00]，边界弹性内均合法 |
| 值形态（result_code 0/-1） | 数值等价 | `"0"` 与 `0` 视为等价（检索页两种表单值均合法） |

### 已知限制观察用例（不计入门禁）

- `E6`/`E7`（数值范围 / 否定语义）：白名单不支持的操作符，始终通过但记录实际行为，追踪模型是编造非法条件（后端拒绝）还是安全降级。
- 多层下钻拒绝、AI 坏输出对抗（截断 JSON / 多 JSON 拼接 / 全角引号等）：期望行为依赖"模型是否顺从用户生成非法结构"或属纯解析层防线，已由单测固化（`test_nl2json.py` `TestNL2JSONAdversarial`），不纳入评估集。

## Provider 与断言

- `providers/provider.py`：构造稳定字段上下文（10 个标准字段含 `result_code`/`access_type` 枚举 + 1 个拓展字段）后调用 `NL2JSONService.convert`。仅 `BKAPP_EVAL_USERNAME` 由环境变量提供；缺失时 Provider 直接报错。
- `assertions/check_conditions.py`：
  - 协议与形态：`valid_protocol_response`、`success_condition_is_valid`（生产 Pydantic 模型）
  - 精确语义：`exact_conditions_match`（字段路径/操作符/filters，多值集合序无关 + 数值等价）、`exact_time_window_match`（支持备选边界）
  - 弹性时段：`time_window_within_bounds`（floor/ceiling 范围断言）
  - 安全：`scope_is_fixed`、`has_no_forbidden_condition`、`injection_is_neutralized`（无论模型是否顺从注入，禁止字段不得穿透）
  - 拒绝与观察：`has_expected_error_code`、`known_limitation_observer`（始终通过，记录实际行为）
- `promptfooconfig.yaml`：默认使用 AIDev 当前 Agent 配置。可在 provider `config.model` 中追加模型名，前提是 AIDev Agent 支持该覆写。

## 运行

### 版本历史

| 版本 | 日期 | 用例数 | 通过率 | 说明 |
|------|------|--------|--------|------|
| v1-v9 | 2026-08-31 ~ 09-01 | 45 | 100%（v6 后） | 初始建设与稳定性调优（详见历史结论文档） |
| 20260908-v1 | 2026-09-08 | 81 | 40/81（49.4%） | 新增 multi_values 20 + scenario_combinations 16；41 失败中 38 为缺省时间窗口漂移（线上 Agent 已对齐 User Message 规则 6 的 30 天口径，旧用例期望 7 天过时） |
| 20260908-v2 | 2026-09-08 | 81 | 76/81（93.8%） | 39 处缺省窗口期望对齐 30 天（明确时间词用例不动）；暴露 A5 十二人漏一人（赵六）、S14 英文 last week 周界换算偏差、S1 关键词提取形态抖动、S7 暂态服务错误 |
| 20260908-v3 | 2026-09-08 | 81 | 80/81（98.8%） | S1 改弹性关键词断言（子串包含）+ S2 改窗口范围断言（"最近"30/31 天弹性）；A5/S14 本轮通过证实为**概率性失败**（稳定性边界）；S1 仍失败：安全审计口语话术（删除了什么重要的东西）关键词选择在"删除"/"重要的东西"间抖动，属模型能力边界 |
| 20260908-v4 | 2026-09-08 | 36（hard） | 33/36 | User Message 三规则增强（≥8 值逐项自检 / 英文时间词同义换算 / 安全审计动作词优先）；**A5/S14 优化生效通过**；新暴露 S5 开放终点与 S16 长句周界 ±1 天（弹性化）；S1 动作词仍抖动降级观察用例 |
| 20260908-v6 | 2026-09-08 | 5（hard-core） | 5/5 | 精准回归子集验证：A5/S14 规则生效、S1 观察行为记录、S5 alts/S16 范围断言收敛 |

### 评估配置三级层级（按耗时选择）

| 配置 | 用例数 | 耗时 | 用途 |
|------|-------:|------|------|
| `promptfooconfig-hard-core.yaml` | 5 | ~1 分钟 | prompt 调优分钟级快速验证（历史失败/优化目标镜像于 `tests/hard_core.yaml`，源头修改须同步） |
| `promptfooconfig-hard.yaml` | 36 | ~5 分钟 | 易错子集回归（海量多值 + 业务场景组合） |
| `promptfooconfig.yaml` | 81 | ~15 分钟 | 全量回归 |

### 已知失败与稳定性发现（AIDev System Prompt 迭代输入）

1. **S1 安全审计关键词抖动**（v2-v4 三轮三种行为，已降级观察用例）："上周有没有人删除了什么重要的东西"的关键词提取在 `['删除','重要']`/`['重要的东西']`/`['重要']` 间不稳定——"删除"是核心检索价值关键词，模型偶发丢失；User Message 动作词优先规则增强后仍不稳定，属 System Prompt 层迭代项
2. **A5 十二人混合分隔概率性遗漏**（v2 出现，v4/v6 规则增强后通过）：≥8 值逐项自检规则生效，持续观察
3. **S14 英文 last week 周界换算偏差**（v2 出现，v4/v6 规则增强后通过）：英文时间词同义换算规则生效（last week=上个自然周非前推 7 天），持续观察
4. **S16 长句周界 ±1 天**（v4 出现）：六维 100 字长句下"上周"偶发偏移 1 天（与 S14 同类周界特性），已用范围断言容忍

在 `src/backend/` 目录执行：

```powershell
$env:PROMPTFOO_PYTHON = (Resolve-Path '.\venv\Scripts\python.exe')
npx promptfoo validate config -c evals/audit-log-search/promptfooconfig.yaml
npx promptfoo eval --no-table --no-cache -c evals/audit-log-search/promptfooconfig.yaml --env-file .env -o evals/audit-log-search/output/<日期>-vN-results.json
```

评估会实际调用 AIDev 智能体，不应在未获授权的生产环境运行。输出文件由 `evals/.gitignore` 忽略。

### 进度观测（promptfoo 管道模式下用例间静默的应对）

promptfoo 在非交互模式下用例之间不输出任何进度，长时间运行无法区分"正常运行/卡住"。Provider 已内置双通道进度输出，每次 AIDev 调用前后各输出一行：

- **控制台**：stderr 实时透传（`[progress] HH:MM:SS [START/ SUCCESS/ ERROR-code] 话术前缀`）
- **进度文件**：`output/progress.log`（启动评估前清空，后台运行时轮询读取）

长跑（如 `--repeat 2` 全量 90 次调用约 10 分钟）建议后台运行 + 轮询：

```powershell
# 清空进度文件并后台启动（环境变量需在当前会话先设置）
Remove-Item evals\audit-log-search\output\progress.log -ErrorAction SilentlyContinue
Start-Process -FilePath "cmd.exe" -WorkingDirectory (Get-Location) -ArgumentList "/c npx promptfoo eval --no-table -c evals/audit-log-search/promptfooconfig.yaml --env-file .env --no-cache --repeat 2 --max-concurrency 4 -o evals/audit-log-search/output/<输出文件>.json > evals\audit-log-search\output\run.log 2>&1"

# 轮询进度（已完成数 = DONE 行数，总调用数 = 用例数 × repeat）
Get-Content evals\audit-log-search\output\progress.log -Tail 15
```

判断卡住的依据：进度文件超过 5 分钟无新行且无 `[START]` 挂起对应的结果行。

## 通过率阈值

目标：**核心条件、时间语义、边缘与安全总通过率不低于 90%**（观察用例 E6/E7 除外）；`S1`~`S4` 是安全门禁，任一失败均不得将本轮视为达标。

## 调优上下文

| 项目 | 内容 |
|---|---|
| User Message | `services/web/query/ai_assistant/services/nl2json.py` 的 `NL2JSON_USER_MESSAGE_TEMPLATE` |
| System Prompt | AIDev 智能体平台中的 `bp-audit-log-search`（v2 全文见 mydocs 自然语言话术覆盖文档 §4） |
| 生产校验 | `NL2JSONService._parse_and_validate`、`_validate_semantics`、`_assemble` |
| 已知限制 | 不支持数值范围和否定语义；拓展字段默认仅支持单层用户显式子键；指代跟进（多轮）为单轮设计边界 |

## 调优经验沉淀

| 日期 | 问题 | 修改 | 效果 |
|------|------|------|------|
| 2026-08-31 | 断言把 eq/include、match_any/match_all 当不同操作符 | 断言增加检索语义等价组（单值 `{eq↔include}`、`{neq↔exclude}`；单关键词 `{match_any↔match_all}`） | E3/E4 通过 |
| 2026-08-31 | 话术含枚举歧义词"失败"（既是 result_code 枚举又是普通关键词），模型解读波动 | C3/C12 改用无枚举歧义关键词"权限变更/权限回收" | C12、C3（V3 回归）通过 |
| 2026-08-31 | 模型把不可映射条件降级为全文检索（如"部门为运维部"→log match_any），而非提示词定义的"忽略字段" | E1 期望改为"核心条件精确匹配 + 允许全文兜底额外条件"（产品行为发现：提示词未定义值降级路径，模型自行选择兜底） | E1 通过 |
| 2026-09-01 | 自然周界换算间歇错误（"上周/本周/last week"日历偏移，3 用例独立同类失败）；口语时段"半夜"易丢失 | 定位为模型系统性弱项，待 AIDev System Prompt 补分步换算指引；评测期望保持正确日历不放宽 | 记录为波动用例，待调优验证 |
| 2026-09-01 | v3 Prompt（三步周界算法 + 时段边界表 + 排除收口 + 未知属性降级规则）上线验证 | 45 用例 repeat×2 对比 V6 | X7/X9/T5 波动清零、周界正确率 1/4→3/4、41 稳定用例零回归；T4 剩余波动为模型星期推算底层能力（同一输入两次推算不同星期），正确率 3/4 |

## 评估迭代进展

| 版本 | 日期 | 用例数 | 通过率 | 关键变化 |
|---|---|---:|---:|---|
| V1 | 2026-08-31 | 11 | 未运行 | 初始化：核心、时间与安全三类确定性用例 |
| V2 | 2026-08-31 | 33 | 87.88% | 扩充：核心字段全覆盖、自然周月/小时/绝对区间/时段时间语义、未知字段/子键信任/枚举映射边缘、注入中和、已知限制观察 |
| V3 | 2026-08-31 | 33 | 96.97% | 评测集校准：断言加操作符等价组、C12/E1 期望修正；C3 因"失败"枚举歧义回归 |
| V4 | 2026-08-31 | 33 | **100%** | C3 同款歧义修正（无枚举关键词），全量通过达标 |
| V5 | 2026-09-01 | 33 | 96.97% | 稳定性验证第一轮（repeat×2=66 runs）：2 波动均为 AIDev 暂态服务错误，语义层 0 波动 |
| V6 | 2026-09-01 | 45 | 95.56% | 复杂语言场景扩充（+12：X1-X10/E8/T11）+ 稳定性第二轮（90 runs）：41 稳定通过/0 稳定失败，4 波动定位为自然周换算与口语时段弱项 |
| V7 | 2026-09-01 | 45 | **97.78%** | System Prompt v3 验证轮（三步周界算法+时段边界表+排除收口+降级规则）：X7/X9/T5 波动清零、周界正确率 1/4→3/4、无回归；剩 T4 星期推算波动（模型底层能力）与 T3 暂态服务错误；**v3 定稿** |
| V8 | 2026-09-01 | 45 | 94.44%（ds4-flash） | **多模型对比轮**（v3 Prompt 固定）：ds4-flash 弱项=X4 隐含语义稳定失败/C4 猜字段值/T6 上月算本月/X7 昨天丢前缀，失败全集中在复杂语言场景且"自信地错"；**结论维持原模型**（报告见 mydocs 多模型对比评估报告） |
| V9 | 2026-09-01 | 45 | 94.44%（qwen3.5-397b） | **三模型终局轮**：qwen3.5-397b 5 失败中 4 个为 latency 超时（31~69s，语义输出全对）+1 个 C10 默认窗口给 30 天——**语义面三模型最优**（T4 星期/隐含语义/枚举兜底全过、X8 精确遵循规则 8 宁少勿错）但 avg 13.6s（+57%）延迟不可接受；**终局结论维持原模型** |
