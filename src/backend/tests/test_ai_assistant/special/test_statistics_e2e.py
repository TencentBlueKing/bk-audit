"""统计生产任务的进程级回归。

真实 gevent Worker、RabbitMQ、MySQL、Redis 和 HTTP SSE；Agent 为本地 HTTP
替身，Doris/IAM 为明确边界替身，不验证引擎兼容或模型生成质量。
"""

import json
import shlex
import time
from pathlib import Path

import pytest
import requests
import yaml
from django.conf import settings

from services.web.ai_assistant.models import Attachment
from tests.test_ai_assistant.celery_integration import wait_for_snapshot
from tests.test_ai_assistant.http_integration import start_http_sse_collector

pytestmark = pytest.mark.django_db(transaction=True, reset_sequences=True)


def completed(attachment):
    """等待生产 Worker 落库，FAILED 立即交由业务断言报告。"""
    result = wait_for_snapshot(
        model=Attachment,
        instance_id=attachment.id,
        predicate=lambda value: value.status in {"SUCCESS", "FAILED"},
    )
    assert result.status == "SUCCESS", (result.error_code, result.error_message)
    return result


def test_ai_statistics_preserves_raw_content_and_http_replay(statistics_stack):
    """保护生产 Task 到数据库、归档及真实 HTTP SSE 的原文契约。"""
    stack = statistics_stack
    attachment = stack.create("AI_STATISTICS", "statistics-success")
    stack.agent.wait_until_started("statistics-success", timeout=settings.CELERY_TEST_TASK_TIMEOUT)
    result = wait_for_snapshot(
        model=Attachment, instance_id=attachment.id, predicate=lambda value: bool(value.stream_config)
    )
    session = requests.Session()
    frames, done, thread, errors = start_http_sse_collector(
        session=session,
        url=f"{stack.web_url}/api/v1/ai_assistant/attachments/{attachment.uid}/stream/",
        params={"execution_id": result.stream_config["execution_id"]},
        headers={"Accept": "text/event-stream"},
        terminal_event="platform.stream_end",
    )
    try:
        deadline = time.monotonic() + settings.CELERY_TEST_TASK_TIMEOUT
        while not frames and time.monotonic() < deadline:
            time.sleep(0.05)
        assert frames, errors
        resume_after = frames[0].stream_id
        resumed, resumed_done, resumed_thread, resumed_errors = start_http_sse_collector(
            session=session,
            url=f"{stack.web_url}/api/v1/ai_assistant/attachments/{attachment.uid}/stream/",
            params={"execution_id": result.stream_config["execution_id"]},
            headers={"Accept": "text/event-stream", "Last-Event-ID": resume_after},
            terminal_event="platform.stream_end",
        )
        # 等重连读到尚未消费的工具帧，确保在终态前建立真实Redis订阅。
        while not resumed and time.monotonic() < deadline:
            time.sleep(0.05)
        assert resumed, resumed_errors
        stack.agent.release("statistics-success")
        assert done.wait(settings.CELERY_TEST_TASK_TIMEOUT)
        assert resumed_done.wait(settings.CELERY_TEST_TASK_TIMEOUT)
        thread.join(timeout=1)
        resumed_thread.join(timeout=1)
        assert not errors
        assert not resumed_errors
        assert [frame.data for frame in resumed] == [frame.data for frame in frames[1:]]
        result = completed(attachment)
        assert result.output_data == {"content": "  ```custom-chart\n非 JSON 原文\n```\n"}
        assert [frame.data for frame in frames] == [event["data"] for event in result.stream_archive]
        assert frames[-1].data == {"status": "SUCCESS"}
        content = [frame.data["delta"] for frame in frames if frame.data.get("type") == "TEXT_MESSAGE_CONTENT"]
        assert content == [result.output_data["content"]]
        snapshot = session.get(
            f"{stack.web_url}/api/v1/ai_assistant/attachments/{attachment.uid}/stream/snapshot/", timeout=10
        )
        assert snapshot.status_code == 200
        assert [event["data"] for event in snapshot.json()["data"]["events"]] == [
            event["data"] for event in result.stream_archive
        ]
    finally:
        stack.agent.release("statistics-success")
        session.close()
    request = stack.agent.requests[-1]
    assert stack.agent.user_headers[-1] == stack.username
    assert request["execute_kwargs"]["thread_id"] == result.stream_config["execution_id"]
    payload = json.loads(request["chat_history"][-1]["content"])
    assert payload["context"]["user"]["username"] == stack.username
    assert payload["instruction"] == "statistics-success"
    assert set(payload["context"]) == {"initial_search_condition", "query_summary", "user"}


def test_ai_statistics_http_truncation_retries_with_new_execution(statistics_stack):
    """HTTP 缺失终止块必须重试，首轮闭合正文不能被当作成功。"""
    stack = statistics_stack
    attachment = stack.create("AI_STATISTICS", "statistics-truncate-once")
    result = completed(attachment)
    attempts = [
        item
        for item in stack.agent.requests
        if json.loads(item["chat_history"][-1]["content"])["instruction"] == "statistics-truncate-once"
    ]
    assert len(attempts) == 2
    assert attempts[0]["execute_kwargs"]["thread_id"] != attempts[1]["execute_kwargs"]["thread_id"]
    assert result.stream_config["execution_id"] == attempts[1]["execute_kwargs"]["thread_id"]
    assert result.task_id == attachment.task_id
    assert result.output_data == {"content": "  重试后的统计正文\n"}
    assert "首轮不可采纳" not in json.dumps(result.stream_archive, ensure_ascii=False)


def test_field_statistics_process_route_persists_complete_snapshot(statistics_stack):
    """生产 Handler 自行投递任务，保护独立队列和最终完整统计包。"""
    attachment = statistics_stack.create("FIELD_STATISTICS")
    result = completed(attachment)
    assert result.task_id == attachment.task_id
    assert not result.is_stream
    assert set(result.output_data) == {
        "field",
        "statistics_kind",
        "overview",
        "distribution",
        "time_series",
        "numeric_summary",
        "query_summary",
    }
    assert result.output_data["field"] == {"raw_name": "extend_data", "keys": ["method"], "display_name": "method"}
    assert result.output_data["statistics_kind"] == "CATEGORICAL"
    assert result.output_data["numeric_summary"] is None
    assert result.output_data["distribution"] == {
        "top_n": 1,
        "has_other": True,
        "groups": [
            {"group_id": "g1", "kind": "VALUE", "value_type": "string", "value": "GET", "count": 6, "ratio": 0.6},
            {"group_id": "g2", "kind": "OTHER", "value_type": None, "value": None, "count": 3, "ratio": 0.3},
            {"group_id": "g3", "kind": "MISSING", "value_type": None, "value": None, "count": 1, "ratio": 0.1},
        ],
    }
    assert result.output_data["time_series"] == {
        "requested_interval": "HOUR",
        "effective_interval": "HOUR",
        "timezone": "Asia/Shanghai",
        "bucket_starts": ["2026-09-15T10:00:00+08:00", "2026-09-15T11:00:00+08:00"],
        "series": [
            {"group_id": "g1", "counts": [2, 4]},
            {"group_id": "g2", "counts": [1, 2]},
            {"group_id": "g3", "counts": [1, 0]},
        ],
    }
    assert result.output_data["query_summary"]["complete"] is True
    assert result.output_data["query_summary"]["total_count"] == 10
    assert result.output_data["overview"] == {
        "total_count": 10,
        "present_count": 9,
        "missing_count": 1,
        "present_ratio": 0.9,
    }
    assert [row["counts"] for row in result.output_data["time_series"]["series"]] == [[2, 4], [1, 2], [1, 0]]
    assert result.output_data["distribution"]["groups"][0]["value"] == "GET"


def test_statistics_declared_worker_subscribes_production_queue():
    """只验证仓库部署声明与任务路由匹配，不声称部署已生效。"""
    definition = yaml.safe_load((Path(__file__).resolve().parents[3] / "app_desc.yaml").read_text())
    command = shlex.split(definition["modules"]["api"]["processes"]["ai-statistics"]["command"])
    assert command[command.index("-Q") + 1] == "ai_assistant_statistics"
    assert command[command.index("-P") + 1] == "gevent"
