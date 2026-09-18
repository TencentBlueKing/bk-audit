"""统计 Task 的确定性生命周期回归。

查询上下文及 Doris 响应使用替身，AI 事件通过回调注入；多数用例直接调用 Task。
程序统计另含真实线程 Worker 重试测试，生产进程和 HTTP 流链路见 special 用例。
"""

import json
import os
import threading
import traceback
from copy import deepcopy
from unittest import mock

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from celery import signals
from celery.exceptions import Ignore, Retry
from django.conf import settings
from django.test import TransactionTestCase, override_settings
from gevent import sleep
from redis.exceptions import RedisError
from requests.exceptions import ConnectionError, Timeout

from api.bk_base.default import SafeQuerySyncResource
from api.bk_plugins_ai_agent.default import ChatCompletion
from core.exceptions import PermissionException
from services.web.ai_assistant.constants import AttachmentType
from services.web.ai_assistant.exceptions import (
    AIStatisticsTimeout,
    AttachmentExportNotSupported,
    AttachmentNotEditable,
    AttachmentOutputValidationError,
    FeedbackNotSupported,
    InvalidAttachmentSource,
)
from services.web.ai_assistant.handlers.audit_statistics import (
    FieldStatisticsAttachmentHandler,
)
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.resources.attachment import (
    ExportAttachment,
    GetAttachment,
    RetryAttachment,
    UpdateAttachment,
)
from services.web.ai_assistant.resources.feedback import UpsertFeedback
from services.web.ai_assistant.services.attachment import AttachmentService
from services.web.ai_assistant.services.attachment_stream import AttachmentStreamService
from services.web.ai_assistant.streaming import RedisLiveStore
from services.web.ai_assistant.tasks.audit_statistics import generate_field_statistics
from services.web.query.ai_assistant.exceptions import (
    LogQueryFailed,
    SensitiveFieldPermissionDenied,
    StatisticsBudgetExceeded,
    UnsupportedFieldType,
)
from services.web.query.ai_assistant.log_tools.context import (
    LogQueryContext,
    LogQueryContextService,
)
from tests.test_ai_assistant.base import (
    AIAssistantPlatformTestCase,
    make_condition,
    make_log_search_output,
)
from tests.test_ai_assistant.celery_integration import (
    running_celery_worker,
    wait_for_snapshot,
)
from tests.test_ai_assistant.handlers import use_attachment_handler
from tests.test_ai_assistant.stream_cleanup import delete_attachment_stream_keys
from tests.test_ai_assistant.test_attachment_task import invoke_task
from tests.test_ai_assistant.test_audit_statistics_handler import (
    AIStatisticsTestMixin,
    FieldStatisticsTestMixin,
)
from tests.test_query.test_ai_assistant.test_field_statistics import field_frames

REAL_CONTEXT_BUILD = LogQueryContextService.build


class FieldStatisticsTaskTest(FieldStatisticsTestMixin, AIAssistantPlatformTestCase):
    """错范围、预览代替全量、任务结果泄露和错误重试均有行为断言。"""

    def setUp(self):
        super().setUp()
        condition = deepcopy(self.source.input_data["condition"])
        condition.update(start_time="2026-09-15T10:00:00+08:00", end_time="2026-09-15T11:59:59+08:00")
        self.source.input_data = {"condition": condition}
        output = deepcopy(self.source.output_data)
        output["query_summary"]["time_range"] = {key: condition[key] for key in ("start_time", "end_time")}
        self.source.output_data = output
        self.source.save(update_record=False, update_fields=["input_data", "output_data"])
        self.context = self.enterContext(
            mock.patch(
                "services.web.query.ai_assistant.log_tools.statistics.LogQueryContextService.build",
                side_effect=self.build_context,
            )
        )
        self.remote = self.enterContext(
            mock.patch.object(SafeQuerySyncResource, "bulk_request", side_effect=self.query)
        )
        self.frames = field_frames()

    def build_context(self, *, username, namespace, condition):
        """替换 IAM/表配置外部边界；断言真实任务传下的完整服务端范围。"""
        self.assertEqual(username, self.user)
        self.assertEqual(namespace, "bkaudit")
        self.assertEqual(condition.model_dump(mode="json"), self.source.input_data["condition"])
        return LogQueryContext(username=username, namespace=namespace, condition=condition, table="logs", conditions=())

    def query(self, requests):
        """模拟同一最终查询的完整统计帧，结果总数10独立于来源2条预览。"""
        if "CAST(group_count AS STRING) AS group_count" in requests[0]["sql"]:
            return ({"list": [dict(group_count="3", invalid_type_count="0", invalid_number_count="0")]},)
        return ({"list": deepcopy(self.frames)},)

    def processing(self):
        """通过公开创建入口获得待执行对象。"""
        return Attachment.objects.get(uid=self.create(top_n=1, interval="HOUR")["uid"])

    def test_success_contract(self):
        attachment = self.processing()
        result = invoke_task(generate_field_statistics, attachment=attachment)
        self.assertEqual(result, {"status": "SUCCESS"})
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, "SUCCESS")
        self.assertEqual(
            attachment.output_data["overview"],
            dict(total_count=10, present_count=9, missing_count=1, present_ratio=0.9),
        )
        self.assertEqual(attachment.output_data["time_series"]["series"][0]["counts"], [2, 4])
        self.assertEqual(attachment.output_data["statistics_kind"], "CATEGORICAL")
        self.assertEqual(
            GetAttachment().request(attachment_uid=str(attachment.uid))["output_data"], attachment.output_data
        )
        self.assertIsNotNone(attachment.finished_at)
        self.assertFalse(attachment.is_stream)

    def test_success_cannot_be_edited_exported_or_feedbacked(self):
        attachment = self.processing()
        invoke_task(generate_field_statistics, attachment=attachment)
        uid = str(attachment.uid)
        with self.assertRaises(AttachmentNotEditable):
            UpdateAttachment().request(attachment_uid=uid, output_data={"content": "overwrite"})
        with self.assertRaises(AttachmentExportNotSupported):
            ExportAttachment().request(attachment_uid=uid, export_format="MARKDOWN")
        with mock.patch(
            "services.web.ai_assistant.resources.feedback.get_request_username", return_value=self.user
        ), self.assertRaises(FeedbackNotSupported):
            UpsertFeedback().request(source_type="ATTACHMENT", source_uid=uid, feedback_type="LIKE")

    def test_client_numeric_hint_cannot_turn_string_field_into_numeric(self):
        attachment = Attachment.objects.get(
            uid=self.create(
                field={"raw_name": "extend_data", "keys": ["method"], "field_type": "double"},
                top_n=1,
                interval="HOUR",
            )["uid"]
        )
        invoke_task(generate_field_statistics, attachment=attachment)
        result = GetAttachment().request(attachment_uid=str(attachment.uid))["output_data"]
        self.assertEqual(result["statistics_kind"], "CATEGORICAL")
        self.assertIsNone(result["numeric_summary"])

    def test_failure_contract(self):
        attachment = self.processing()
        self.context.side_effect = SensitiveFieldPermissionDenied()
        with self.assertRaises(SensitiveFieldPermissionDenied):
            invoke_task(generate_field_statistics, attachment=attachment)
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, "FAILED")
        self.assertIsNone(attachment.output_data)
        self.assertEqual(self.remote.call_count, 0)

    def test_public_failure_preserves_only_controlled_log_tool_diagnostics(self):
        """公开轮询保留权限、类型及预算诊断，不泄露底层消息或 data。"""
        for error_type in (SensitiveFieldPermissionDenied, UnsupportedFieldType, StatisticsBudgetExceeded):
            with self.subTest(error_type=error_type.__name__):
                attachment = self.processing()
                error = error_type(message="SELECT secret FROM logs", data={"secret": "raw"})
                self.context.side_effect = error
                with self.assertRaises(error_type):
                    invoke_task(generate_field_statistics, attachment=attachment)
                result = GetAttachment().request(attachment_uid=str(attachment.uid))
                self.assertEqual(result["status"], "FAILED")
                self.assertEqual(result["error_code"], error.code)
                self.assertEqual(result["error_message"], str(error.MESSAGE))
                self.assertIsNone(result["output_data"])
                self.assertNotIn("SELECT secret", str(result))

    def test_unknown_failure_stays_sanitized_and_stale_failure_cannot_overwrite(self):
        """任意来源异常仍脱敏；查询中接管后旧任务不能写错误终态。"""
        attachment = self.processing()
        self.context.side_effect = RuntimeError("SELECT secret FROM logs")
        with self.assertRaises(RuntimeError):
            invoke_task(generate_field_statistics, attachment=attachment)
        result = GetAttachment().request(attachment_uid=str(attachment.uid))
        self.assertEqual(result["error_code"], "TASK_EXECUTION_FAILED")
        self.assertEqual(result["error_message"], "附件执行失败，请稍后重试")
        self.assertIsNone(result["output_data"])

        attachment = self.processing()

        def supersede(**kwargs):
            """模拟查询鉴权期间新任务接管。"""
            Attachment.objects.filter(id=attachment.id).update(task_id="replacement")
            raise SensitiveFieldPermissionDenied()

        self.context.side_effect = supersede
        with self.assertRaises(SensitiveFieldPermissionDenied):
            invoke_task(generate_field_statistics, attachment=attachment)
        result = GetAttachment().request(attachment_uid=str(attachment.uid))
        self.assertEqual(result["status"], "PROCESSING")
        self.assertEqual(result["error_code"], "")

    def test_doris_failure_and_retry_do_not_expose_upstream_body(self):
        """真实统计错误包装保留重试分类，日志与Celery异常只含安全摘要。"""
        marker = "PRIVATE_DORIS_STATISTICS_10"
        for retries in (0, generate_field_statistics.max_retries):
            with self.subTest(retries=retries):
                attachment = self.processing()
                self.remote.side_effect = APIRequestError(status_code=503, result={"message": marker})
                if retries == 0:
                    with self.assertRaises(Retry) as raised:
                        invoke_task(generate_field_statistics, attachment=attachment, retries=retries)
                    self.assertNotIn(marker, str(raised.exception))
                    self.assertNotIn(marker, str(raised.exception.exc))
                    self.assertNotIn(marker, "".join(traceback.format_exception(raised.exception)))
                else:
                    with self.assertLogs("services.web.ai_assistant.tasks.base", level="ERROR") as captured:
                        with self.assertRaises(Exception) as raised:
                            invoke_task(generate_field_statistics, attachment=attachment, retries=retries)
                    self.assertNotIn(marker, "\n".join(captured.output))
                    self.assertNotIn(marker, str(raised.exception))

    def test_retry_contract(self):
        for error in (ConnectionError("unavailable"), Timeout("late"), APIRequestError(status_code=503)):
            with self.subTest(error=type(error).__name__):
                attachment = self.processing()
                self.remote.side_effect = error
                with self.assertRaises(Retry) as raised:
                    invoke_task(generate_field_statistics, attachment=attachment)
                self.assertEqual(raised.exception.sig.id, attachment.task_id)
                attachment.refresh_from_db()
                self.assertEqual(attachment.status, "PROCESSING")
                self.assertIsNotNone(attachment.last_activity_at)
                self.remote.side_effect = self.query
                self.assertEqual(
                    invoke_task(generate_field_statistics, attachment=attachment, retries=1), {"status": "SUCCESS"}
                )

    def test_failed_field_statistics_can_be_manually_retried(self):
        """真实 Resource 重启失败程序统计，轮换任务并持久化重新计算的完整结果。"""
        attachment = self.processing()
        self.remote.side_effect = ValueError("temporary backend failure")
        with self.assertRaises(LogQueryFailed):
            invoke_task(generate_field_statistics, attachment=attachment)
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, "FAILED")
        old_task_id = attachment.task_id
        old_context = deepcopy(attachment.context_data)
        with mock.patch.object(generate_field_statistics, "apply_async") as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                retried = RetryAttachment().request(attachment_uid=str(attachment.uid))
        self.assertEqual(retried["status"], "PROCESSING")
        attachment.refresh_from_db()
        self.assertNotEqual(attachment.task_id, old_task_id)
        self.assertEqual(attachment.context_data, old_context)
        dispatch.assert_called_once()
        self.remote.side_effect = self.query
        self.assertEqual(invoke_task(generate_field_statistics, attachment=attachment), {"status": "SUCCESS"})
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, "SUCCESS")
        self.assertEqual(attachment.output_data["statistics_kind"], "CATEGORICAL")

    def test_stale_task_contract(self):
        attachment = self.processing()
        Attachment.objects.filter(id=attachment.id).update(task_id="replacement")
        with self.assertRaises(Ignore):
            invoke_task(generate_field_statistics, attachment=attachment)
        self.assertEqual(self.remote.call_count, 0)
        attachment.refresh_from_db()
        self.assertEqual(attachment.task_id, "replacement")
        self.assertEqual(attachment.status, "PROCESSING")

    def test_finish_cas_does_not_return_success_for_stale_worker(self):
        attachment = self.processing()

        def supersede(requests):
            """查询过程中模拟新任务接管，旧包不能覆盖。"""
            result = self.query(requests)
            Attachment.objects.filter(id=attachment.id).update(task_id="new-task")
            return result

        self.remote.side_effect = supersede
        with self.assertRaises(Ignore):
            invoke_task(generate_field_statistics, attachment=attachment)
        attachment.refresh_from_db()
        self.assertIsNone(attachment.output_data)

    def test_non_temporary_upstream_and_invalid_frames_do_not_retry(self):
        for error in (
            APIRequestError(status_code=403),
            APIRequestError(status_code=400),
            ValueError("invalid response"),
        ):
            with self.subTest(error=error):
                attachment = self.processing()
                self.remote.side_effect = error
                with self.assertRaises(Exception) as raised:
                    invoke_task(generate_field_statistics, attachment=attachment)
                self.assertNotIsInstance(raised.exception, Retry)
                attachment.refresh_from_db()
                self.assertEqual(attachment.status, "FAILED")

    def test_retry_exhaustion_finishes_failed(self):
        attachment = self.processing()
        self.remote.side_effect = Timeout("late")
        with self.assertRaises(Exception) as raised:
            invoke_task(generate_field_statistics, attachment=attachment, retries=generate_field_statistics.max_retries)
        self.assertNotIsInstance(raised.exception, Retry)
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, "FAILED")

    def test_execution_rechecks_source_status_owner_and_clear(self):
        for change in ("status", "owner", "clear"):
            with self.subTest(change=change):
                attachment = self.processing()
                if change == "clear":
                    Conversation.objects.filter(id=self.conversation.id).update(is_deleted=True)
                else:
                    Message.objects.filter(id=self.source.id).update(
                        **({"status": "FAILED"} if change == "status" else {"created_by": "other"})
                    )
                with self.assertRaises(InvalidAttachmentSource):
                    invoke_task(generate_field_statistics, attachment=attachment)
                self.assertEqual(self.remote.call_count, 0)
                Message.objects.filter(id=self.source.id).update(status="SUCCESS", created_by=self.user)
                Conversation.objects.filter(id=self.conversation.id).update(is_deleted=False)

    def test_history_is_independent_of_later_queries(self):
        first = self.processing()
        invoke_task(generate_field_statistics, attachment=first)
        first_snapshot = GetAttachment().request(attachment_uid=str(first.uid))["output_data"]
        self.frames[2]["d0_json"] = '"POST"'
        second = self.processing()
        invoke_task(generate_field_statistics, attachment=second)
        self.assertEqual(GetAttachment().request(attachment_uid=str(first.uid))["output_data"], first_snapshot)
        self.assertEqual(
            GetAttachment().request(attachment_uid=str(second.uid))["output_data"]["distribution"]["groups"][0][
                "value"
            ],
            "POST",
        )

    def test_task_uses_field_budget(self):
        self.assertEqual(generate_field_statistics.queue, "ai_assistant_statistics")
        self.assertEqual(generate_field_statistics.time_limit, settings.AI_ASSISTANT_FIELD_STATISTICS_TASK_TIMEOUT)
        self.assertEqual(generate_field_statistics.rate_limit, settings.AI_ASSISTANT_FIELD_STATISTICS_TASK_RATE_LIMIT)

    def test_revoked_system_permission_is_rechecked_before_query(self):
        attachment = self.processing()
        self.context.side_effect = REAL_CONTEXT_BUILD
        with mock.patch(
            "services.web.query.ai_assistant.log_tools.context.SearchLogPermission.has_system_search_permission",
            return_value=False,
        ), mock.patch(
            "services.web.query.ai_assistant.log_tools.context."
            "SearchLogPermission.raise_system_view_permission_exception",
            side_effect=PermissionException(action_name="view_system", permission={}, apply_url=""),
        ), self.assertRaises(
            PermissionException
        ):
            invoke_task(generate_field_statistics, attachment=attachment)
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, "FAILED")
        self.assertEqual(self.remote.call_count, 0)

    @override_settings(AI_ASSISTANT_FIELD_STATISTICS_BUSINESS_TIMEOUT=0.001)
    def test_business_timeout_retries_before_hard_kill(self):
        attachment = self.processing()
        self.remote.side_effect = lambda requests: sleep(0.01)
        with self.assertRaises(Retry):
            invoke_task(generate_field_statistics, attachment=attachment)
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, "PROCESSING")

    def test_json_roundtrip_preserves_boolean_and_numeric_identity(self):
        for kind, literal, expected in (("boolean", "true", True), ("number", "2", 2), ("string", '"2"', "2")):
            with self.subTest(kind=kind):
                self.frames[2].update(d0_type=kind, d0_json=literal)
                self.frames[1]["a"] = "6" if kind == "number" else "0"
                attachment = self.processing()
                invoke_task(generate_field_statistics, attachment=attachment)
                value = GetAttachment().request(attachment_uid=str(attachment.uid))["output_data"]["distribution"][
                    "groups"
                ][0]["value"]
                self.assertEqual(value, expected)
                self.assertIs(type(value), type(expected))


class FieldStatisticsWorkerIntegrationTest(TransactionTestCase):
    """真实隔离 Broker/Worker 重试，验证生产 Task 返回值和最终数据库快照。"""

    available_apps = ["services.web.ai_assistant"]
    queue = f"{settings.CELERY_TEST_QUEUE_PREFIX}_{os.getpid()}_field_statistics"

    @classmethod
    def setUpClass(cls):
        """在 available_apps 缩小注册表前启动 Worker，保留真实 Django 系统检查。"""
        super().setUpClass()
        cls.worker_context = running_celery_worker(queue_name=cls.queue)
        cls.worker_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        """停止专属 Worker 并让 fixture 清理隔离队列。"""
        cls.worker_context.__exit__(None, None, None)
        super().tearDownClass()

    def test_worker_retry_keeps_task_id_and_persists_status_only_result(self):
        use_attachment_handler(self, FieldStatisticsAttachmentHandler())
        user = "statistics-worker"
        conversation = Conversation.objects.create(created_by=user, updated_by=user)
        condition = make_condition()
        condition.start_time = "2026-09-15T10:00:00+08:00"
        condition.end_time = "2026-09-15T11:59:59+08:00"
        output = make_log_search_output().model_dump(mode="json")
        output["query_summary"]["time_range"] = {"start_time": condition.start_time, "end_time": condition.end_time}
        source = Message.objects.create(
            conversation=conversation,
            message_type="LOG_SEARCH",
            status="SUCCESS",
            created_by=user,
            updated_by=user,
            input_data={"condition": condition.model_dump(mode="json")},
            context_data={
                "username": user,
                "namespace": "bkaudit",
                "system_id": condition.scope_id,
                "source": "field_condition",
            },
            output_data=output,
        )
        finished = threading.Event()
        deliveries = []
        results = []
        remote_calls = []
        original_apply = generate_field_statistics.apply_async

        def dispatch(*args, **kwargs):
            """只把测试投递路由到本进程隔离队列，保留生产任务和重试实现。"""
            kwargs["queue"] = self.queue
            return original_apply(*args, **kwargs)

        def query(requests):
            """首个远端请求断连，重试提供完整帧。"""
            remote_calls.append(requests)
            if len(remote_calls) == 1:
                raise ConnectionError("temporary")
            if "CAST(group_count AS STRING) AS group_count" in requests[0]["sql"]:
                return ({"list": [dict(group_count="3", invalid_type_count="0", invalid_number_count="0")]},)
            return ({"list": field_frames()},)

        def on_task_done(sender=None, task_id=None, retval=None, state=None, **kwargs):
            """捕获真实Worker退出的返回值，不依赖ignore_result结果后端。"""
            if sender is generate_field_statistics._get_current_object():
                deliveries.append((task_id, state))
                if state == "SUCCESS":
                    results.append(retval)
                    finished.set()

        signals.task_postrun.connect(on_task_done, weak=False)
        try:
            with mock.patch.object(generate_field_statistics, "apply_async", side_effect=dispatch), mock.patch(
                "services.web.ai_assistant.tasks.audit_statistics.get_exponential_backoff_interval",
                return_value=0,
            ), mock.patch.object(SafeQuerySyncResource, "bulk_request", side_effect=query), mock.patch(
                "services.web.query.ai_assistant.log_tools.statistics.LogQueryContextService.build",
                return_value=LogQueryContext(
                    username=user, namespace="bkaudit", condition=condition, table="logs", conditions=()
                ),
            ):
                attachment = AttachmentService(user=user).create(
                    source_message_uid=str(source.uid),
                    attachment_type=AttachmentType.FIELD_STATISTICS,
                    input_data={
                        "field": {"raw_name": "extend_data", "keys": ["method"]},
                        "top_n": 1,
                        "interval": "HOUR",
                    },
                )
                completed = wait_for_snapshot(
                    model=Attachment, instance_id=attachment.id, predicate=lambda item: item.status == "SUCCESS"
                )
                self.assertTrue(finished.wait(timeout=settings.CELERY_TEST_TASK_TIMEOUT))
                self.assertEqual(results, [{"status": "SUCCESS"}])
                self.assertEqual(deliveries, [(attachment.task_id, "RETRY"), (attachment.task_id, "SUCCESS")])
                self.assertEqual(completed.output_data["overview"]["total_count"], 10)
        finally:
            signals.task_postrun.disconnect(on_task_done)


class AIStatisticsTaskTest(AIStatisticsTestMixin, AIAssistantPlatformTestCase):
    """保留真实平台、数据库及流；仅替换远端 Agent。"""

    def setUp(self):
        """清理仅属于本测试附件的 Redis 流，不影响其他执行。"""
        super().setUp()
        self.stream_uids = []
        self.addCleanup(lambda: delete_attachment_stream_keys(attachment_uids=self.stream_uids))

    def processing(self):
        """公开入口创建流式统计附件。"""
        attachment = Attachment.objects.get(uid=self.create()["uid"])
        self.stream_uids.append(str(attachment.uid))
        return attachment

    @staticmethod
    def events(content, message_id="final", closed=True):
        """构造 Agent 标准文本帧，不对正文格式作预处理。"""
        result = [
            {"type": "TEXT_MESSAGE_START", "messageId": message_id, "role": "assistant"},
            {"type": "TEXT_MESSAGE_CONTENT", "messageId": message_id, "delta": content},
        ]
        if closed:
            result.append({"type": "TEXT_MESSAGE_END", "messageId": message_id})
        return result

    def run_events(self, attachment, events, **kwargs):
        """远端替身按真实 on_event 回调输入原始事件。"""

        def respond(**request):
            for event in events:
                request["on_event"](event)

        with mock.patch.object(api.bk_plugins_ai_agent, "chat_completion", side_effect=respond) as agent:
            result = invoke_task(self.handler.async_task, attachment=attachment, **kwargs)
        return result, agent.call_args.kwargs

    def test_non_sse_upstream_error_does_not_leak_body_to_task_logs(self):
        """实际callback解析收到业务错误时，任务日志与异常不得包含上游正文。"""
        attachment = self.processing()
        marker = "PRIVATE_STATISTICS_BODY_10"
        response = mock.Mock(status_code=200, headers={"Content-Type": "application/json"})
        response.json.return_value = {"result": False, "code": 1001, "message": marker}

        def respond(**request):
            """只替换HTTP边界，真实执行callback响应解析。"""
            resource = ChatCompletion()
            token = resource._on_event_context.set(request["on_event"])
            try:
                return resource.parse_response(response)
            finally:
                resource._on_event_context.reset(token)

        with mock.patch.object(api.bk_plugins_ai_agent, "chat_completion", side_effect=respond):
            with self.assertRaises(Retry) as retried:
                invoke_task(self.handler.async_task, attachment=attachment)
            self.assertNotIn(marker, "".join(traceback.format_exception(retried.exception)))
            self.assertNotIn(marker, str(retried.exception.exc))
            with self.assertLogs("services.web.ai_assistant.tasks.base", level="ERROR") as captured:
                with self.assertRaises(Exception) as raised:
                    invoke_task(
                        self.handler.async_task, attachment=attachment, retries=self.handler.async_task.max_retries
                    )
        self.assertNotIn(marker, "\n".join(captured.output))
        self.assertNotIn(marker, str(raised.exception))
        result = GetAttachment().request(attachment_uid=str(attachment.uid))
        self.assertEqual(result["status"], "FAILED")
        self.assertNotIn(marker, str(result))

    def test_success_contract(self):
        attachment = self.processing()
        content = "  ```custom-chart\nnot-json\n```\n"
        events = [
            *self.events("过程", "first"),
            {"type": "CUSTOM", "name": "arbitrary", "value": {"x": 1}},
            *self.events(content),
            {"type": "RUN_FINISHED", "result": {"ignored": True}},
        ]
        result, request = self.run_events(attachment, events)
        attachment.refresh_from_db()
        self.assertEqual(result, {"status": "SUCCESS"})
        self.assertEqual(attachment.output_data, {"content": content})
        self.assertEqual(
            GetAttachment().request(attachment_uid=str(attachment.uid))["output_data"], {"content": content}
        )
        self.assertEqual(request["agent_code"], "bp-ai-log-stats")
        self.assertEqual(request["user"], self.user)
        self.assertEqual([entry["role"] for entry in request["chat_history"]], ["role", "user"])
        payload = json.loads(request["chat_history"][1]["content"])
        self.assertEqual(set(payload), {"instruction", "context"})
        self.assertEqual(set(payload["context"]), {"initial_search_condition", "query_summary", "user"})
        self.assertEqual(payload["context"]["initial_search_condition"], self.source.input_data["condition"])
        self.assertEqual(set(payload["context"]["query_summary"]), {"total", "executed_at"})
        self.assertEqual(
            payload["context"]["user"], {"username": self.user, "timezone": "Asia/Shanghai", "language": "zh-cn"}
        )
        for forbidden in ("samples", "namespace", "sql", "attachment_id", "message_id"):
            self.assertNotIn(forbidden, json.dumps(payload))
        self.assertEqual(
            request["execute_kwargs"], {"stream": True, "thread_id": str(attachment.stream_config["execution_id"])}
        )
        archived = [
            item["data"]
            for item in attachment.stream_archive
            if item["event"] not in ("platform.stream_reset", "platform.stream_end")
        ]
        self.assertEqual(archived, events)

    def test_failure_contract(self):
        for events in (self.events(" \n"), self.events("完整", "a") + self.events("未闭合", "b", False), []):
            with self.subTest(events=events):
                attachment = self.processing()
                with self.assertRaises(AttachmentOutputValidationError):
                    self.run_events(attachment, events, retries=self.handler.async_task.max_retries)
                attachment.refresh_from_db()
                self.assertEqual(attachment.status, "FAILED")
                self.assertIsNone(attachment.output_data)
                self.assertEqual(attachment.stream_archive[-1]["data"], {"status": "FAILED"})

    def test_retry_contract(self):
        attachment = self.processing()
        task_id = attachment.task_id
        attachment.context_data["system_prompt"] = "创建时的统计提示词"
        attachment.save(update_fields=["context_data"])
        original_context = deepcopy(attachment.context_data)
        with mock.patch.object(api.bk_plugins_ai_agent, "chat_completion", side_effect=Timeout()) as first:
            with self.assertRaises(Retry) as caught:
                invoke_task(self.handler.async_task, attachment=attachment)
        attachment.refresh_from_db()
        first_execution = attachment.stream_config["execution_id"]
        self.assertEqual(attachment.status, "PROCESSING")
        self.assertEqual(caught.exception.sig.kwargs, {"attachment_id": attachment.pk, "task_id": task_id})
        result, second = self.run_events(attachment, self.events(" 无数据\n"), retries=1)
        attachment.refresh_from_db()
        self.assertEqual(result, {"status": "SUCCESS"})
        self.assertEqual(attachment.task_id, task_id)
        self.assertNotEqual(attachment.stream_config["execution_id"], first_execution)
        self.assertEqual(attachment.context_data, original_context)
        self.assertEqual(first.call_args.kwargs["chat_history"], second["chat_history"])
        self.assertEqual(second["chat_history"][0]["content"], "创建时的统计提示词")
        self.assertNotEqual(
            first.call_args.kwargs["execute_kwargs"]["thread_id"], second["execute_kwargs"]["thread_id"]
        )

    def test_manual_retry_rotates_task_and_agent_execution_then_keeps_history(self):
        """失败原对象经公开手动重试后更换两层执行 ID，历史文本独立保存。"""
        attachment = self.processing()
        with self.assertRaises(AttachmentOutputValidationError):
            self.run_events(attachment, self.events("未闭合", closed=False), retries=self.handler.async_task.max_retries)
        attachment.refresh_from_db()
        old_task = attachment.task_id
        old_execution = attachment.stream_config["execution_id"]
        with self.captureOnCommitCallbacks(execute=True):
            RetryAttachment().request(attachment_uid=str(attachment.uid))
        attachment.refresh_from_db()
        self.assertNotEqual(attachment.task_id, old_task)
        _, request = self.run_events(attachment, self.events("历史正文"))
        attachment.refresh_from_db()
        self.assertNotEqual(request["execute_kwargs"]["thread_id"], old_execution)
        self.assertEqual(attachment.output_data, {"content": "历史正文"})
        other = self.processing()
        self.run_events(other, self.events("另一个统计"))
        detail = GetAttachment().request(attachment_uid=str(attachment.uid))
        self.assertEqual(detail["output_data"], {"content": "历史正文"})

    def test_stale_task_contract(self):
        attachment = self.processing()
        Attachment.objects.filter(pk=attachment.pk).update(task_id="new-task")
        with mock.patch.object(api.bk_plugins_ai_agent, "chat_completion") as agent, self.assertRaises(Ignore):
            invoke_task(self.handler.async_task, attachment=attachment)
        agent.assert_not_called()

    def test_invalid_source_and_identity_fail_before_agent(self):
        for mutation in ("source", "identity", "cleared"):
            with self.subTest(mutation=mutation):
                attachment = self.processing()
                if mutation == "source":
                    Message.objects.filter(pk=self.source.pk).update(status="FAILED")
                elif mutation == "identity":
                    context = deepcopy(attachment.context_data)
                    context["username"] = "other"
                    Attachment.objects.filter(pk=attachment.pk).update(context_data=context)
                else:
                    Conversation.objects.filter(pk=self.conversation.pk).update(is_deleted=True)
                with mock.patch.object(api.bk_plugins_ai_agent, "chat_completion") as agent:
                    with self.assertRaises(InvalidAttachmentSource):
                        invoke_task(self.handler.async_task, attachment=attachment)
                agent.assert_not_called()
                Message.objects.filter(pk=self.source.pk).update(status="SUCCESS")

    def test_permission_errors_do_not_retry(self):
        attachment = self.processing()
        with mock.patch.object(
            api.bk_plugins_ai_agent, "chat_completion", side_effect=APIRequestError(status_code=403)
        ):
            with self.assertRaises(APIRequestError):
                invoke_task(self.handler.async_task, attachment=attachment)
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, "FAILED")

    @override_settings(AI_ASSISTANT_AI_STATISTICS_BUSINESS_TIMEOUT=0.001)
    def test_business_timeout_retries_and_exhaustion_has_statistics_message(self):
        """真实 gevent 业务超时在硬终止前完成重试及稳定错误快照。"""
        attachment = self.processing()
        with mock.patch.object(api.bk_plugins_ai_agent, "chat_completion", side_effect=lambda **kwargs: sleep(0.02)):
            with self.assertRaises(Retry):
                invoke_task(self.handler.async_task, attachment=attachment)
            attachment.refresh_from_db()
            self.assertEqual(attachment.status, "PROCESSING")
            with self.assertRaises(AIStatisticsTimeout):
                invoke_task(self.handler.async_task, attachment=attachment, retries=self.handler.async_task.max_retries)
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, "FAILED")
        self.assertEqual(attachment.error_message, "AI 统计超时，请重试")
        self.assertEqual(attachment.error_code, AIStatisticsTimeout().code)
        self.assertEqual(attachment.stream_archive[-1]["data"], {"status": "FAILED"})

    @override_settings(AI_ASSISTANT_AI_STATISTICS_CONTENT_MAX_BYTES=6)
    def test_content_budget_failure_is_sanitized_and_later_complete_message_can_recover(self):
        """UTF-8 超预算只作废候选；安全异常不泄露原文，后续闭合文本可恢复。"""
        sentinel = "PRIVATE_STATISTICS_SENTINEL"
        attachment = self.processing()
        with self.assertLogs("services.web.ai_assistant.tasks.base", level="ERROR") as logs:
            with self.assertRaises(AttachmentOutputValidationError):
                self.run_events(attachment, self.events(sentinel), retries=self.handler.async_task.max_retries)
        self.assertNotIn(sentinel, "\n".join(logs.output))
        self.assertNotIn("input_value", "\n".join(logs.output))
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, "FAILED")
        self.assertNotIn(sentinel, attachment.error_message)
        second = self.processing()
        self.run_events(second, self.events(sentinel, "large") + self.events("中文", "valid"))
        second.refresh_from_db()
        self.assertEqual(second.output_data, {"content": "中文"})

    def test_late_execution_cannot_overwrite_new_task(self):
        """Agent 执行中任务被替换，完成 CAS 必须 Ignore，不能写结果或返回成功。"""
        attachment = self.processing()

        def respond(**request):
            Attachment.objects.filter(pk=attachment.pk).update(task_id="new-task", output_data=None)
            for event in self.events("旧正文"):
                request["on_event"](event)

        with mock.patch.object(api.bk_plugins_ai_agent, "chat_completion", side_effect=respond), self.assertRaises(
            Ignore
        ):
            invoke_task(self.handler.async_task, attachment=attachment)
        attachment.refresh_from_db()
        self.assertEqual(attachment.task_id, "new-task")
        self.assertEqual(attachment.status, "PROCESSING")
        self.assertIsNone(attachment.output_data)

    def test_archive_recovers_raw_text_when_live_redis_fails(self):
        """实时写入降级后仍成功保存文本及原始事件，快照可重建展示。"""
        attachment = self.processing()
        events = self.events("  无数据\n")
        with mock.patch.object(RedisLiveStore, "append", side_effect=RedisError("offline")):
            self.run_events(attachment, events)
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, "SUCCESS")
        self.assertEqual(attachment.output_data, {"content": "  无数据\n"})
        snapshot = AttachmentStreamService(user=self.user).get_snapshot(attachment_uid=attachment.uid)
        self.assertEqual([event.data for event in snapshot.events if event.event is None], events)
        self.assertEqual(snapshot.events[-1].data, {"status": "SUCCESS"})

    def test_success_supports_feedback_but_not_report_edit_or_export(self):
        """AI 统计反馈独立启用，固定文本不能被报告编辑或导出入口改写。"""
        attachment = self.processing()
        self.run_events(attachment, self.events("结果"))
        uid = str(attachment.uid)
        with self.assertRaises(AttachmentNotEditable):
            UpdateAttachment().request(attachment_uid=uid, output_data={"content": "overwrite"})
        with self.assertRaises(AttachmentExportNotSupported):
            ExportAttachment().request(attachment_uid=uid, export_format="MARKDOWN")
        with mock.patch("services.web.ai_assistant.resources.feedback.get_request_username", return_value=self.user):
            feedback = UpsertFeedback().request(source_type="ATTACHMENT", source_uid=uid, feedback_type="LIKE")
        self.assertEqual(feedback["feedback_type"], "LIKE")

    test_stream_success_contract = test_success_contract
    test_stream_retry_contract = test_retry_contract
