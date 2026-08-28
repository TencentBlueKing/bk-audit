"""生产日志分析 Task 在 gevent Worker 硬退出后的 RabbitMQ 重投验证。"""

import pytest
from django.conf import settings

from services.web.ai_assistant.constants import ExecutionStatus, PlatformStreamEvent
from services.web.ai_assistant.models import Attachment
from services.web.ai_assistant.schemas import parse_stream_config
from services.web.ai_assistant.streaming import RedisLiveStore
from tests.test_ai_assistant.celery_integration import wait_for_snapshot
from tests.test_ai_assistant.special.process_worker import (
    kill_worker_process,
    running_worker_process,
)

pytestmark = pytest.mark.django_db(transaction=True, reset_sequences=True)


def test_log_analysis_sigkill_redelivers_production_task(log_analysis_redelivery_stack):
    """gevent Worker 硬退出后，RabbitMQ 以同一 task ID 重投生产分析任务。"""

    stack = log_analysis_redelivery_stack
    worker_options = {
        "queue_name": stack.queue_name,
        "include_modules": ("services.web.ai_assistant.tasks.audit_analysis",),
        "extra_env": stack.worker_env,
        "enable_special_handlers": False,
        "pool": "gevent",
        "concurrency": 1,
        "log_scene": "log-analysis-redelivery",
    }
    with running_worker_process(**worker_options) as worker_a:
        attachment = stack.create_attachment(
            user="log-analysis-redelivery-user",
            instruction="redelivery",
        )
        stack.agent.wait_until_started("redelivery", timeout=settings.CELERY_TEST_TASK_TIMEOUT)
        started = wait_for_snapshot(
            model=Attachment,
            instance_id=attachment.id,
            predicate=lambda value: bool(value.stream_config),
        )
        original_task_id = started.task_id
        old_config = parse_stream_config(started.stream_config)
        kill_worker_process(worker_a)
        stack.agent.release("redelivery")

    with running_worker_process(**worker_options):
        completed = wait_for_snapshot(
            model=Attachment,
            instance_id=attachment.id,
            predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
        )
    new_config = parse_stream_config(completed.stream_config)
    old_events = (
        RedisLiveStore()
        .read(
            redis_key=old_config.redis_key,
            after_id="0-0",
            block_ms=1,
        )
        .events
    )

    assert completed.task_id == original_task_id
    assert stack.agent.attempts["redelivery"] == 2
    assert new_config.execution_id != old_config.execution_id
    assert new_config.redis_key != old_config.redis_key
    assert any(event.event == PlatformStreamEvent.STREAM_RESET for event in old_events)
    assert completed.output_data == {"markdown": "# 重投结论"}
