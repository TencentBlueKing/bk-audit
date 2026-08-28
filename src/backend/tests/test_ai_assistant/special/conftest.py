from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings

from tests.test_ai_assistant.special.fake_log_analysis_agent import (
    FakeLogAnalysisAgent,
    running_fake_log_analysis_agent,
)
from tests.test_ai_assistant.special.process_worker import (
    running_worker_process,
    using_test_broker,
)
from tests.test_ai_assistant.special.web_process import running_gunicorn_web

AttachmentFactory = Callable[..., Any]

SPECIAL_TEST_ROOT = Path(__file__).parent
LOG_ANALYSIS_TEST_USER = "log-analysis-e2e-user"


def prefixed_queue(name: str) -> str:
    return f"{settings.CELERY_TEST_QUEUE_PREFIX}_{name}"


@dataclass(frozen=True, slots=True)
class LogAnalysisStack:
    username: str
    web_url: str
    queue_name: str
    task_name: str
    agent: FakeLogAnalysisAgent
    create_attachment: AttachmentFactory


@dataclass(frozen=True, slots=True)
class LogAnalysisRedeliveryStack:
    queue_name: str
    task_name: str
    agent: FakeLogAnalysisAgent
    worker_env: dict[str, str]
    create_attachment: AttachmentFactory


def log_analysis_worker_env(agent: FakeLogAnalysisAgent) -> dict[str, str]:
    """返回生产日志分析 Worker 的专项配置，保证常规与重投用例使用同一参数。"""

    return {
        "BKAPP_AI_AUDIT_LOG_ANALYSIS_API_URL": agent.base_url,
        "BKAPP_AI_ASSISTANT_LOG_ANALYSIS_BUSINESS_TIMEOUT": "10",
        "BKAPP_AI_ASSISTANT_LOG_ANALYSIS_TASK_RATE_LIMIT": "1000/m",
        "BKAPP_AI_ASSISTANT_LOG_ANALYSIS_TASK_TIMEOUT": "15",
    }


def create_log_analysis_attachment(*, user: str, instruction: str):
    """创建绑定成功 LOG_SEARCH 快照的生产 AI_ANALYSIS Attachment。"""

    from services.web.ai_assistant.constants import (
        AnalysisMode,
        AttachmentType,
        ExecutionStatus,
        MessageType,
    )
    from services.web.ai_assistant.models import Conversation, Message
    from services.web.ai_assistant.services import AttachmentService
    from tests.test_ai_assistant.base import make_condition, make_log_search_output

    conversation = Conversation.objects.create(created_by=user, updated_by=user)
    condition = make_condition()
    source = Message.objects.create(
        conversation=conversation,
        message_type=MessageType.LOG_SEARCH,
        status=ExecutionStatus.SUCCESS,
        input_data={"condition": condition.model_dump(mode="json")},
        context_data={
            "username": user,
            "namespace": "bkaudit",
            "system_id": condition.scope_id,
            "source": "field_condition",
        },
        output_data=make_log_search_output().model_dump(mode="json"),
        created_by=user,
        updated_by=user,
    )
    return AttachmentService(user=user).create(
        source_message_uid=str(source.uid),
        attachment_type=AttachmentType.AI_ANALYSIS,
        input_data={"analysis_mode": AnalysisMode.CUSTOM, "instruction": instruction},
    )


@contextmanager
def using_task_queue(task: Any, queue_name: str) -> Iterator[None]:
    """临时切换 Task 队列，并隔离 Celery 首次投递后缓存的执行选项。"""

    missing = object()
    original_queue = task.queue
    original_exec_options = task.__dict__.pop("_exec_options", missing)
    task.queue = queue_name
    try:
        yield
    finally:
        task.queue = original_queue
        task.__dict__.pop("_exec_options", None)
        if original_exec_options is not missing:
            task.__dict__["_exec_options"] = original_exec_options


@pytest.fixture(scope="module")
def log_analysis_stack(django_db_setup):
    """组合生产日志分析 Task 所需的真实本地组件。"""

    from services.web.ai_assistant.constants import AttachmentType
    from services.web.ai_assistant.handlers.audit_analysis import AIAnalysisHandler
    from services.web.ai_assistant.handlers.registry import attachment_handler_registry
    from services.web.ai_assistant.tasks.audit_analysis import execute_log_analysis

    original_handler = attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
    attachment_handler_registry.register(AIAnalysisHandler())
    queue_name = prefixed_queue("ai_assistant_log_analysis")
    with running_fake_log_analysis_agent() as agent:
        with using_task_queue(execute_log_analysis, queue_name):
            try:
                with (
                    using_test_broker(queue_name=queue_name),
                    running_worker_process(
                        queue_name=queue_name,
                        include_modules=("services.web.ai_assistant.tasks.audit_analysis",),
                        extra_env=log_analysis_worker_env(agent),
                        enable_special_handlers=False,
                        pool="gevent",
                        concurrency=2,
                        log_scene="log-analysis-e2e",
                        observe_task_postrun=True,
                    ),
                    running_gunicorn_web(username=LOG_ANALYSIS_TEST_USER) as web_url,
                ):
                    yield LogAnalysisStack(
                        username=LOG_ANALYSIS_TEST_USER,
                        web_url=web_url,
                        queue_name=queue_name,
                        task_name=execute_log_analysis.name,
                        agent=agent,
                        create_attachment=create_log_analysis_attachment,
                    )
            finally:
                attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
                if original_handler is not None:
                    attachment_handler_registry.register(original_handler)


@pytest.fixture
def log_analysis_redelivery_stack(django_db_setup):
    """提供不预启 Worker 的生产 Task 运行栈，由用例控制 SIGKILL 和接管顺序。"""

    from services.web.ai_assistant.constants import AttachmentType
    from services.web.ai_assistant.handlers.audit_analysis import AIAnalysisHandler
    from services.web.ai_assistant.handlers.registry import attachment_handler_registry
    from services.web.ai_assistant.models import Attachment
    from services.web.ai_assistant.tasks.audit_analysis import execute_log_analysis
    from tests.test_ai_assistant.stream_cleanup import delete_attachment_stream_keys

    original_handler = attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
    attachment_handler_registry.register(AIAnalysisHandler())
    queue_name = prefixed_queue("ai_assistant_log_analysis_redelivery")
    with running_fake_log_analysis_agent() as agent:
        with using_task_queue(execute_log_analysis, queue_name):
            try:
                with using_test_broker(queue_name=queue_name):
                    yield LogAnalysisRedeliveryStack(
                        queue_name=queue_name,
                        task_name=execute_log_analysis.name,
                        agent=agent,
                        worker_env=log_analysis_worker_env(agent),
                        create_attachment=create_log_analysis_attachment,
                    )
            finally:
                leftovers = delete_attachment_stream_keys(
                    attachment_uids=Attachment.objects.filter(is_stream=True).values_list("uid", flat=True)
                )
                attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
                if original_handler is not None:
                    attachment_handler_registry.register(original_handler)
                if leftovers:
                    raise AssertionError(f"日志分析重投专项 Redis key 残留: {leftovers}")


def pytest_collection_modifyitems(items):
    """special/ 目录默认打 special marker，避免漏标后进入常规门禁。"""

    marker = pytest.mark.special
    for item in items:
        if not Path(item.path).is_relative_to(SPECIAL_TEST_ROOT):
            continue
        if item.get_closest_marker("special") is None:
            item.add_marker(marker)
