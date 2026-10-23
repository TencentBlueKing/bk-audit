# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations
under the License.
We undertake not to change the open source license (MIT license) that applies
to the current version of the project delivered to anyone in the future.

F4.5 全量导出同步直出编排测试（MessageExportService.export_or_fallback）。

覆盖：开关回退（A10）/ 快照 total 准入（A2）/ 同步成功 / 降级标记（A15）/
权限与白名单转换（A11/A12）/ 快照解析失败 / export_config 同源预处理（A14 轻量）。
Runner 内部守卫由 tests.test_query.test_ai_assistant.test_sync_export 覆盖，此处全 mock。
"""

from unittest import mock
from uuid import uuid4

from django.test import override_settings

from core.exceptions import ValidationError as RequestValidationError
from services.web.ai_assistant.exceptions import (
    InvalidMessageSnapshot,
    LogExportPermissionDenied,
)
from services.web.ai_assistant.services.log_export import MessageExportService
from services.web.query.ai_assistant.constants import SYNC_EXPORT_FALLBACK
from services.web.query.ai_assistant.exceptions import (
    AIOutputInvalidError,
    AIPermissionDeniedError,
    SyncExportFallback,
)
from services.web.query.ai_assistant.services.export import PreviewExportFile
from services.web.query.constants import TaskEnum
from services.web.query.models import LogExportTask
from services.web.query.tasks import (
    process_log_export_task,
    process_one_log_export_task,
)
from tests.test_ai_assistant.base import (
    TARGET_SYSTEM_ID,
    AIAssistantPlatformTestCase,
    make_log_search_output,
)

LOG_EXPORT_MODULE = "services.web.ai_assistant.services.log_export"

SYNC_ENABLED_SETTINGS = dict(
    AI_EXPORT_SYNC_ENABLED=True,
    AI_EXPORT_SYNC_MAX_COUNT=100,
)


@override_settings(**SYNC_ENABLED_SETTINGS)
class TestExportOrFallback(AIAssistantPlatformTestCase):
    """同步优先、超限自动降级的编排边界。"""

    def setUp(self):
        super().setUp()
        self.service = MessageExportService(user=self.user)

    def test_timeout_fallback_creates_task_without_blocking_count(self):
        """同步超时后HTTP只创建任务，不能再次执行可能耗时300秒的count。"""
        message = self.create_log_search_message(output=make_log_search_output(total=2))
        with (
            mock.patch(f"{LOG_EXPORT_MODULE}.SyncExportRunner.run", side_effect=SyncExportFallback(reason="deadline")),
            mock.patch(
                "services.web.query.ai_assistant.services.export.SearchLogPermission.has_system_search_permission",
                return_value=True,
            ),
            mock.patch(
                "services.web.query.export.data_fetcher.DataFetcher.get_total",
                side_effect=AssertionError("HTTP must not count"),
            ),
            mock.patch("services.web.query.resources.doris.process_one_log_export_task.apply_async"),
        ):
            result = self.service.export_or_fallback(message_uid=str(message.uid), export_config={})
        task = LogExportTask.objects.get(id=result["export_task_id"])
        self.assertEqual(task.status, TaskEnum.READY)
        self.assertEqual(task.total, 0)
        self.assertEqual(task.export_config["source"], "ai_assistant")
        self.assertEqual(result["export_type"], SYNC_EXPORT_FALLBACK)

    @override_settings(LOG_EXPORT_MAX_COUNT=100)
    def test_worker_rejects_excessive_total_without_scheduling_it_again(self):
        """延后count仍执行上限检查，确定性超限不被周期调度重复查询。"""
        task = LogExportTask.objects.create(
            namespace="default",
            name="bounded-export",
            status=TaskEnum.READY,
            query_params={},
            export_config={"source": "ai_assistant", "field_scope": "specified", "fields": []},
        )
        with (
            mock.patch("services.web.query.export.data_fetcher.DataFetcher.get_total", return_value=101),
            mock.patch(
                "services.web.query.export.data_fetcher.DataFetcher.fetch_patch_logs",
                side_effect=AssertionError("must reject before data fetch"),
            ),
            mock.patch("services.web.query.tasks.BKRepoUploader"),
        ):
            process_one_log_export_task.run(task.id)
        task.refresh_from_db()
        self.assertEqual(task.status, TaskEnum.FAILURE)
        self.assertEqual(task.total, 101)
        self.assertEqual(task.current_records, 0)
        self.assertIn("101", task.error_msg)
        with mock.patch("services.web.query.tasks.process_one_log_export_task.apply_async") as dispatch:
            process_log_export_task.run(task_id=task.id)
            dispatch.assert_not_called()

    @override_settings(LOG_EXPORT_MAX_COUNT=100)
    def test_known_excessive_ready_task_fails_instead_of_staying_ready(self):
        """下调上限后，历史待处理任务应转失败且不再查询或调度。"""
        task = LogExportTask.objects.create(
            namespace="default",
            name="lowered-limit",
            status=TaskEnum.READY,
            total=101,
            query_params={},
            export_config={},
        )
        with mock.patch("services.web.query.tasks.process_one_log_export_task.apply_async") as dispatch:
            process_log_export_task.run(task_id=task.id)
            dispatch.assert_called_once_with(kwargs={"task_id": task.id})
        with mock.patch("services.web.query.export.data_fetcher.DataFetcher.get_total") as count:
            process_one_log_export_task.run(task.id)
            count.assert_not_called()
        task.refresh_from_db()
        self.assertEqual(task.status, TaskEnum.FAILURE)
        self.assertIn("101", task.error_msg)
        with mock.patch("services.web.query.tasks.process_one_log_export_task.apply_async") as dispatch:
            process_log_export_task.run(task_id=task.id)
            dispatch.assert_not_called()

    def test_disabled_by_settings_falls_back_to_async(self):
        """A10：开关关闭 → 100% 现行为（异步任务），同步执行器零触达。"""

        message = self.create_log_search_message(output=make_log_search_output(total=2))
        with mock.patch(f"{LOG_EXPORT_MODULE}.SyncExportRunner") as mock_runner_cls:
            with mock.patch(
                f"{LOG_EXPORT_MODULE}.FullExportService.create_task",
                return_value={"id": 1, "status": "READY"},
            ) as mock_create:
                with override_settings(AI_EXPORT_SYNC_ENABLED=False):
                    result = self.service.export_or_fallback(message_uid=str(message.uid), export_config={})

        self.assertEqual(result, {"export_task_id": 1, "status": "READY"})
        mock_create.assert_called_once()
        # 开关关闭：同步执行器不实例化（行为与历史完全一致）
        mock_runner_cls.assert_not_called()

    def test_snapshot_total_exceed_falls_back_async_without_sync_attempt(self):
        """A2：快照 total 超准入上限 → 直接异步（不占并发槽、不查 Doris、Runner 零触达）。"""

        message = self.create_log_search_message(output=make_log_search_output(total=500))
        with mock.patch(f"{LOG_EXPORT_MODULE}.SyncExportRunner") as mock_runner_cls:
            with mock.patch(
                f"{LOG_EXPORT_MODULE}.FullExportService.create_task",
                return_value={"id": 2, "status": "READY"},
            ) as mock_create:
                result = self.service.export_or_fallback(message_uid=str(message.uid), export_config={})

        self.assertEqual(result, {"export_task_id": 2, "status": "READY"})
        # 直接异步（准入拦截）不带降级标记——降级标记仅用于"尝试同步后转异步"的分流提示
        self.assertNotIn("export_type", result)
        mock_runner_cls.assert_not_called()
        mock_create.assert_called_once()

    def test_sync_success_returns_file_with_shared_export_config(self):
        """同步成功：返回文件对象；Runner 收到 _build_export_config 同源处理后的配置。"""

        message = self.create_log_search_message(output=make_log_search_output(total=2))
        expected_file = PreviewExportFile(content=b"xlsx-bytes", file_name="AI助手检索导出-abc.xlsx")
        with mock.patch(f"{LOG_EXPORT_MODULE}.SyncExportRunner") as mock_runner_cls:
            mock_runner_cls.return_value.run.return_value = expected_file
            result = self.service.export_or_fallback(message_uid=str(message.uid), export_config={})

        self.assertIs(result, expected_file)
        # Runner 构造参数：条件来自快照、身份为当前用户、export_config 经同源预处理
        _, kwargs = mock_runner_cls.call_args
        self.assertEqual(kwargs["condition"].scope_id, TARGET_SYSTEM_ID)
        self.assertEqual(kwargs["username"], self.user)
        self.assertEqual(kwargs["export_config"]["source"], "ai_assistant")
        # ai_standard 默认翻译为 SPECIFIED + 快照默认列（与异步导出同构）
        self.assertEqual(kwargs["export_config"]["field_scope"], "specified")
        self.assertEqual(len(kwargs["export_config"]["fields"]), 9)

    def test_runner_fallback_creates_async_task_with_marker(self):
        """A15：Runner 降级信号 → 自动转异步链路，响应带 export_type=sync_fallback 标记。"""

        message = self.create_log_search_message(output=make_log_search_output(total=2))
        with mock.patch(f"{LOG_EXPORT_MODULE}.SyncExportRunner") as mock_runner_cls:
            mock_runner_cls.return_value.run.side_effect = SyncExportFallback("deadline")
            with mock.patch(
                f"{LOG_EXPORT_MODULE}.FullExportService.create_task",
                return_value={"id": 9, "status": "READY"},
            ) as mock_create:
                result = self.service.export_or_fallback(message_uid=str(message.uid), export_config={})

        self.assertEqual(result, {"export_task_id": 9, "status": "READY", "export_type": SYNC_EXPORT_FALLBACK})
        mock_create.assert_called_once()

    def test_runner_permission_denied_converted(self):
        """A11：同步路径权限拒绝 → 平台稳定错误码（不降级不吞异常）。"""

        message = self.create_log_search_message(output=make_log_search_output(total=2))
        with mock.patch(f"{LOG_EXPORT_MODULE}.SyncExportRunner") as mock_runner_cls:
            mock_runner_cls.return_value.run.side_effect = AIPermissionDeniedError()
            with mock.patch(f"{LOG_EXPORT_MODULE}.FullExportService.create_task") as mock_create:
                with self.assertRaises(LogExportPermissionDenied):
                    self.service.export_or_fallback(message_uid=str(message.uid), export_config={})
        # 权限失败是用户错误：不降级创建任务
        mock_create.assert_not_called()

    def test_runner_invalid_config_converted_400(self):
        """A12：同步路径越权字段 → 400 参数错误（与异步路径同一转换语义）。"""

        message = self.create_log_search_message(output=make_log_search_output(total=2))
        with mock.patch(f"{LOG_EXPORT_MODULE}.SyncExportRunner") as mock_runner_cls:
            mock_runner_cls.return_value.run.side_effect = AIOutputInvalidError()
            with self.assertRaises(RequestValidationError) as caught:
                self.service.export_or_fallback(message_uid=str(message.uid), export_config={})
        self.assertEqual(caught.exception.STATUS_CODE, 400)

    def test_invalid_snapshot_output_raises(self):
        """快照 output 损坏（无法预判 total）→ InvalidMessageSnapshot，不静默分流。"""

        message = self.create_log_search_message(output=make_log_search_output(total=2))
        message.output_data = {"broken": True}
        message.save(update_fields=["output_data"])

        with self.assertRaises(InvalidMessageSnapshot):
            self.service.export_or_fallback(message_uid=str(message.uid), export_config={})

    def test_flatten_extension_passed_through_to_runner(self):
        """A14（轻量）：flatten_extension 开关经同源预处理透传给 Runner；
        extension_keys 完整注入链由 create_full_export 既有用例覆盖（同一 _build_export_config）。"""

        message = self.create_log_search_message(output=make_log_search_output(total=2))
        with mock.patch(f"{LOG_EXPORT_MODULE}.SyncExportRunner") as mock_runner_cls:
            mock_runner_cls.return_value.run.return_value = PreviewExportFile(content=b"x", file_name="a.xlsx")
            self.service.export_or_fallback(
                message_uid=str(message.uid),
                export_config={"flatten_extension": True},
            )

        _, kwargs = mock_runner_cls.call_args
        self.assertTrue(kwargs["export_config"]["flatten_extension"])
        self.assertEqual(kwargs["export_config"]["source"], "ai_assistant")

    def test_full_export_regression_unchanged(self):
        """回归锚点：create_full_export 直连入口行为不变（重构等价性证明之一）。"""

        message = self.create_log_search_message(output=make_log_search_output(total=2))
        with mock.patch(
            f"{LOG_EXPORT_MODULE}.FullExportService.create_task",
            return_value={"id": 3, "status": "PENDING"},
        ) as mock_create:
            result = self.service.create_full_export(message_uid=str(message.uid), export_config={})

        self.assertEqual(result, {"export_task_id": 3, "status": "PENDING"})
        mock_create.assert_called_once()
        # 随机 uid 防字符串巧合断言：任务名模板以 AI助手检索导出- 开头
        task_name = mock_create.call_args.kwargs["task_name"]
        self.assertTrue(str(task_name).startswith("AI助手检索导出-"))
        self.assertNotEqual(str(message.uid), str(uuid4()))
