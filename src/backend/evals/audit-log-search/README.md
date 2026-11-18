# 审计日志检索评测（已退役）

自然语言检索不再走独立消息类型。条件组装的解析、语义校验和默认时间窗由
`ConditionAssemblyService` 承担，单测在 `tests/test_query/test_ai_assistant/test_nl2json.py`。

Agent 规划与完整条件集合的评测请使用 `evals/intent-recognition`。
本目录的 provider 只返回退役错误，不再调用智能体。
