# -*- coding: utf-8 -*-
"""已退役的审计日志检索评测入口。

自然语言入口已收敛到用户意图规划，条件组装由公共条件服务承担。
本目录不再调用智能体。请使用 evals/intent-recognition。
"""


def call_api(prompt, options, context):
    """promptfoo 入口：明确返回退役错误，避免静默通过。"""

    return {"error": "audit-log-search 评测已退役，请使用 evals/intent-recognition"}
