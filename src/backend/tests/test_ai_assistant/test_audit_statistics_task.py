"""程序统计真实 Task 生命周期；仅替换远端 Doris 和系统元数据依赖。"""

import os
import threading
import traceback
from copy import deepcopy
from unittest import mock

from bk_resource.exceptions import APIRequestError
from celery import signals
from celery.exceptions import Ignore, Retry
from django.conf import settings
from django.test import TransactionTestCase, override_settings
from gevent import sleep
from requests.exceptions import ConnectionError, Timeout

from api.bk_base.default import SafeQuerySyncResource
from core.exceptions import PermissionException
from services.web.ai_assistant.constants import AttachmentType
from services.web.ai_assistant.exceptions import (
    AttachmentExportNotSupported,
    AttachmentNotEditable,
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
    UpdateAttachment,
)
from services.web.ai_assistant.resources.feedback import UpsertFeedback
from services.web.ai_assistant.services.attachment import AttachmentService
from services.web.ai_assistant.tasks.audit_statistics import generate_field_statistics
from services.web.query.ai_assistant.exceptions import (
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
from tests.test_ai_assistant.test_attachment_task import invoke_task
from tests.test_ai_assistant.test_audit_statistics_handler import (
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
        if "AS group_count" in requests[0]["sql"]:
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
            if "AS group_count" in requests[0]["sql"]:
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
