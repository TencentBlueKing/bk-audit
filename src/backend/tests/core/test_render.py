# -*- coding: utf-8 -*-

from core.render import jinja_render


def test_jinja_render():
    template_value = "render: {{content.title}} {{content.content}} {{title}}"
    context = {"content": {"title": "title", "content": "content"}, "title": "title"}
    actual = jinja_render(template_value, context)
    assert actual == "render: title content title"

    template_value = "{{risk_id}} {{event_data.a}} {{event_evidence.b}} {{event_evidence.c}}"
    context = {
        "risk_id": "20240801152805764050",
        "event_content": "测试风险",
        "raw_event_id": "1hdsajdksa8eqw9e9wppppjdkazmds",
        "strategy_id": 295,
        "event_evidence": {"b": 2},
        "event_type": [],
        "event_data": {"a": 1},
        "event_time": "2024-08-01 14:20:19",
        "event_end_time": "2024-08-01 14:20:19",
        "event_source": "",
        "operator": ["oaozhang"],
        "status": "new",
        "rule_id": None,
        "rule_version": None,
        "origin_operator": [],
        "current_operator": [],
        "notice_users": ["psychyang"],
        "tags": [505],
        "risk_label": "normal",
        "last_operate_time": "2024-08-01 15:28:05",
        "permission": {"edit_risk_v2": True},
        "ticket_history": [],
    }
    actual = jinja_render(template_value, context)
    assert actual == "20240801152805764050 1 2 "
