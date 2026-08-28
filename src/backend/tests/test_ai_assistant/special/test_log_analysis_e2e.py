"""日志分析生产 Task 的真实 RabbitMQ/Redis/MySQL/SSE 闭环验证。"""

import json
import time

import pytest
import requests
from django.conf import settings

from services.web.ai_assistant.constants import ExecutionStatus, PlatformStreamEvent
from services.web.ai_assistant.exceptions import LogAnalysisTimeout
from services.web.ai_assistant.models import Attachment
from services.web.ai_assistant.schemas import parse_stream_config
from services.web.ai_assistant.streaming import RedisLiveStore
from tests.test_ai_assistant.celery_integration import wait_for_snapshot
from tests.test_ai_assistant.http_integration import start_http_sse_collector
from tests.test_ai_assistant.special.process_worker import (
    clear_process_task_postrun,
    observe_process_task_postrun,
    wait_for_process_task_postrun,
)
from tests.test_ai_assistant.stream_cleanup import delete_attachment_stream_keys

pytestmark = pytest.mark.django_db(transaction=True, reset_sequences=True)


def attachment_service(user: str):
    # 延迟到 special fixture 运行期导入，避免仅收集模块就污染全局 Handler 注册表。
    from services.web.ai_assistant.services import AttachmentService

    return AttachmentService(user=user)


@pytest.fixture(autouse=True)
def cleanup_log_analysis_streams():
    yield
    for attachment in Attachment.objects.filter(status=ExecutionStatus.PROCESSING):
        wait_for_terminal(attachment)
    for task_id in Attachment.objects.exclude(task_id="").values_list("task_id", flat=True):
        clear_process_task_postrun(task_id)
    leftovers = delete_attachment_stream_keys(
        attachment_uids=Attachment.objects.filter(is_stream=True).values_list("uid", flat=True)
    )
    if leftovers:
        raise AssertionError(f"日志分析专项 Redis key 残留: {leftovers}")


def wait_for_terminal(attachment: Attachment) -> Attachment:
    return wait_for_snapshot(
        model=Attachment,
        instance_id=attachment.id,
        predicate=lambda value: value.status in {ExecutionStatus.SUCCESS, ExecutionStatus.FAILED},
    )


def get_stream_snapshot(log_analysis_stack, attachment: Attachment) -> dict:
    response = requests.get(
        f"{log_analysis_stack.web_url}/api/v1/ai_assistant/attachments/{attachment.uid}/stream/snapshot/",
        timeout=(3.05, settings.CELERY_TEST_TASK_TIMEOUT),
    )
    assert response.status_code == 200, response.text
    envelope = response.json()
    assert envelope["result"] is True, envelope
    return envelope["data"]


def test_log_analysis_streams_and_persists_final_markdown(log_analysis_stack):
    assert log_analysis_stack.task_name == "ai_assistant.execute_log_analysis"
    assert log_analysis_stack.queue_name.endswith("_ai_assistant_log_analysis")
    attachment = log_analysis_stack.create_attachment(
        user=log_analysis_stack.username,
        instruction="success",
    )
    log_analysis_stack.agent.wait_until_started(
        "success",
        timeout=settings.CELERY_TEST_TASK_TIMEOUT,
    )
    config = parse_stream_config(
        wait_for_snapshot(
            model=Attachment,
            instance_id=attachment.id,
            predicate=lambda value: bool(value.stream_config),
        ).stream_config
    )
    session = requests.Session()
    frames, done, thread, errors = start_http_sse_collector(
        session=session,
        url=f"{log_analysis_stack.web_url}/api/v1/ai_assistant/attachments/{attachment.uid}/stream/",
        params={"execution_id": str(config.execution_id)},
        headers={"Accept": "text/event-stream"},
        terminal_event=PlatformStreamEvent.STREAM_END,
    )
    deadline = time.monotonic() + settings.CELERY_TEST_TASK_TIMEOUT
    try:
        while time.monotonic() < deadline:
            if any(frame.data.get("type") == "TOOL_CALL_START" for frame in frames if isinstance(frame.data, dict)):
                break
            time.sleep(0.05)
        else:
            raise AssertionError(f"SSE 未在任务完成前收到工具事件: frames={frames}, errors={errors}")
    finally:
        log_analysis_stack.agent.release("success")
    assert done.wait(settings.CELERY_TEST_TASK_TIMEOUT)
    thread.join(timeout=1)
    session.close()
    assert not errors, errors
    completed = wait_for_snapshot(
        model=Attachment,
        instance_id=attachment.id,
        predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
    )

    assert completed.output_data == {"markdown": "# 审计结论"}
    agent_request = log_analysis_stack.agent.requests[-1]
    assert agent_request["chat_history"] == []
    assert agent_request["execute_kwargs"] == {"stream": True}
    assert any(frame.data.get("type") == "TOOL_CALL_START" for frame in frames if isinstance(frame.data, dict))
    assert frames[-1].event == PlatformStreamEvent.STREAM_END
    assert [frame.data for frame in frames] == [event["data"] for event in completed.stream_archive]


@pytest.mark.parametrize("instruction", ["run-error", "disconnect"])
def test_log_analysis_agent_failures_close_stream(log_analysis_stack, instruction):
    attachment = log_analysis_stack.create_attachment(
        user=log_analysis_stack.username,
        instruction=instruction,
    )

    log_analysis_stack.agent.wait_until_started(
        instruction,
        timeout=settings.CELERY_TEST_TASK_TIMEOUT,
    )
    config = parse_stream_config(
        wait_for_snapshot(
            model=Attachment,
            instance_id=attachment.id,
            predicate=lambda value: bool(value.stream_config),
        ).stream_config
    )
    session = requests.Session()
    frames, done, thread, errors = start_http_sse_collector(
        session=session,
        url=f"{log_analysis_stack.web_url}/api/v1/ai_assistant/attachments/{attachment.uid}/stream/",
        params={"execution_id": str(config.execution_id)},
        headers={"Accept": "text/event-stream"},
        terminal_event=PlatformStreamEvent.STREAM_END,
    )
    deadline = time.monotonic() + settings.CELERY_TEST_TASK_TIMEOUT
    try:
        while time.monotonic() < deadline:
            if any(frame.data.get("type") == "RUN_STARTED" for frame in frames if isinstance(frame.data, dict)):
                break
            if done.is_set():
                raise AssertionError(f"SSE 在收到 RUN_STARTED 前关闭: frames={frames}, errors={errors}")
            time.sleep(0.05)
        else:
            raise AssertionError(f"SSE 未实时收到 RUN_STARTED: frames={frames}, errors={errors}")
        log_analysis_stack.agent.release(instruction)
        assert done.wait(settings.CELERY_TEST_TASK_TIMEOUT)
    finally:
        log_analysis_stack.agent.release(instruction)
        thread.join(timeout=1)
        session.close()
    assert not errors, errors
    completed = wait_for_terminal(attachment)
    snapshot = get_stream_snapshot(log_analysis_stack, completed)

    assert completed.status == ExecutionStatus.FAILED
    assert completed.output_data is None
    assert completed.stream_archive[-1] == {
        "event": PlatformStreamEvent.STREAM_END,
        "stream_id": None,
        "data": {"status": ExecutionStatus.FAILED},
    }
    assert snapshot["events"] == completed.stream_archive
    assert frames[-1].event == PlatformStreamEvent.STREAM_END
    assert frames[-1].data == {"status": ExecutionStatus.FAILED}
    assert [frame.data for frame in frames] == [event["data"] for event in completed.stream_archive]
    if instruction == "run-error":
        assert any(event["data"].get("type") == "RUN_ERROR" for event in completed.stream_archive[:-1])


def test_log_analysis_manual_retry_rotates_execution_and_resets_old_stream(log_analysis_stack):
    attachment = log_analysis_stack.create_attachment(
        user=log_analysis_stack.username,
        instruction="retry-once",
    )
    failed = wait_for_terminal(attachment)
    assert failed.status == ExecutionStatus.FAILED
    old_task_id = failed.task_id
    old_config = parse_stream_config(failed.stream_config)

    retried = attachment_service(log_analysis_stack.username).retry(attachment_uid=str(failed.uid))
    completed = wait_for_snapshot(
        model=Attachment,
        instance_id=attachment.id,
        predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
    )
    new_config = parse_stream_config(completed.stream_config)
    old_live_events = (
        RedisLiveStore()
        .read(
            redis_key=old_config.redis_key,
            after_id="0-0",
            block_ms=1,
        )
        .events
    )

    assert retried.uid == failed.uid == completed.uid
    assert retried.task_id != old_task_id
    assert new_config.execution_id != old_config.execution_id
    assert any(event.event == PlatformStreamEvent.STREAM_RESET for event in old_live_events)
    assert completed.output_data == {"markdown": "# 重试结论"}
    assert not any(event["data"].get("type") == "RUN_ERROR" for event in completed.stream_archive[:-1])
    assert log_analysis_stack.agent.attempts["retry-once"] == 2


def test_log_analysis_manual_retry_fences_old_production_execution(log_analysis_stack):
    """重复投递先令旧 task 失败，手动重试后阻塞中的旧执行不得覆盖新产物。"""

    from services.web.ai_assistant.tasks.audit_analysis import execute_log_analysis

    attachment = log_analysis_stack.create_attachment(
        user=log_analysis_stack.username,
        instruction="fencing",
    )
    log_analysis_stack.agent.wait_until_started("fencing", timeout=settings.CELERY_TEST_TASK_TIMEOUT)
    old_task_id = attachment.task_id
    observe_process_task_postrun(old_task_id)
    try:
        execute_log_analysis.apply_async(
            kwargs={"attachment_id": attachment.id, "task_id": old_task_id},
            task_id=old_task_id,
        )
        failed = wait_for_terminal(attachment)
        assert failed.status == ExecutionStatus.FAILED

        retried = attachment_service(log_analysis_stack.username).retry(attachment_uid=str(failed.uid))
        completed = wait_for_snapshot(
            model=Attachment,
            instance_id=attachment.id,
            predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
        )
        expected_config = completed.stream_config
        expected_archive = completed.stream_archive
        log_analysis_stack.agent.release("fencing")
        wait_for_process_task_postrun(task_id=old_task_id, expected_count=2)
    finally:
        log_analysis_stack.agent.release("fencing")
        clear_process_task_postrun(old_task_id)
    completed.refresh_from_db()

    assert retried.task_id != old_task_id
    assert completed.task_id == retried.task_id
    assert completed.status == ExecutionStatus.SUCCESS
    assert completed.output_data == {"markdown": "# 新任务结论"}
    assert completed.stream_config == expected_config
    assert completed.stream_archive == expected_archive
    assert not any(event["data"].get("delta") == "# 旧执行不应覆盖" for event in completed.stream_archive)
    assert log_analysis_stack.agent.attempts["fencing"] == 3


def test_log_analysis_two_users_are_isolated_under_real_gevent_worker(log_analysis_stack):
    expected = {
        "log-analysis-user-a": "# 用户 A 结论",
        "log-analysis-user-b": "# 用户 B 结论",
    }
    attachments = {
        user: log_analysis_stack.create_attachment(user=user, instruction=f"user:{user}") for user in expected
    }
    log_analysis_stack.agent.wait_for_user_pair(timeout=settings.CELERY_TEST_TASK_TIMEOUT)

    completed = {user: wait_for_terminal(attachment) for user, attachment in attachments.items()}
    configs = {user: parse_stream_config(attachment.stream_config) for user, attachment in completed.items()}
    request_contexts = {
        json.loads(request["input"])["context"]["user"]["username"] for request in log_analysis_stack.agent.requests
    }

    assert all(attachment.status == ExecutionStatus.SUCCESS for attachment in completed.values())
    assert {user: attachment.output_data["markdown"] for user, attachment in completed.items()} == expected
    assert len({config.execution_id for config in configs.values()}) == 2
    assert len({config.redis_key for config in configs.values()}) == 2
    assert set(expected).issubset(request_contexts)

    foreign = completed["log-analysis-user-a"]
    snapshot_response = requests.get(
        f"{log_analysis_stack.web_url}/api/v1/ai_assistant/attachments/{foreign.uid}/stream/snapshot/",
        timeout=(3.05, settings.CELERY_TEST_TASK_TIMEOUT),
    )
    stream_response = requests.get(
        f"{log_analysis_stack.web_url}/api/v1/ai_assistant/attachments/{foreign.uid}/stream/",
        params={"execution_id": str(configs["log-analysis-user-a"].execution_id)},
        headers={"Accept": "text/event-stream"},
        timeout=(3.05, settings.CELERY_TEST_TASK_TIMEOUT),
    )
    assert snapshot_response.status_code == 404
    assert snapshot_response.json()["result"] is False
    assert stream_response.status_code == 404
    assert stream_response.json()["result"] is False


def test_log_analysis_gevent_business_timeout_precedes_hard_limit(log_analysis_stack):
    attachment = log_analysis_stack.create_attachment(
        user=log_analysis_stack.username,
        instruction="timeout",
    )
    log_analysis_stack.agent.wait_until_started("timeout", timeout=settings.CELERY_TEST_TASK_TIMEOUT)
    try:
        completed = wait_for_terminal(attachment)
    finally:
        log_analysis_stack.agent.release("timeout")

    elapsed = (completed.finished_at - completed.started_at).total_seconds()
    assert completed.status == ExecutionStatus.FAILED
    assert completed.error_code == LogAnalysisTimeout().code
    assert completed.output_data is None
    assert 8 <= elapsed < 15
    assert completed.stream_archive[-1]["event"] == PlatformStreamEvent.STREAM_END
