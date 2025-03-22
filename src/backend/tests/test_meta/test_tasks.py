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
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from unittest import mock

from django.test import TestCase

from apps.meta.constants import SystemDiagnosisPushStatusEnum
from apps.meta.handlers.system_diagnosis import SystemDiagnosisPushHandler
from apps.meta.models import System, SystemDiagnosisConfig
from apps.meta.tasks import update_system_diagnosis_push


class TestUpdateSystemDiagnosisPush(TestCase):
    def setUp(self):
        # 为了捕获定时任务中对 logger_celery 的调用，这里进行 patch
        patcher_info = mock.patch("apps.meta.tasks.logger_celery.info")
        self.mock_logger_celery_info = patcher_info.start()
        self.addCleanup(patcher_info.stop)

        patcher_error = mock.patch("apps.meta.tasks.logger_celery.error")
        self.mock_logger_celery_error = patcher_error.start()
        self.addCleanup(patcher_error.stop)

    def tearDown(self):
        mock.patch.stopall()

    def test_skip_update_when_not_enabled_and_no_config(self):
        """
        场景1：系统未开启诊断推送，且没有关联配置（或配置状态非PUSH），应跳过更新
        """
        system = System.objects.create(system_id="system_skip", name="System Skip", enable_system_diagnosis_push=False)
        # 未创建 SystemDiagnosisConfig
        with mock.patch.object(SystemDiagnosisPushHandler, "change_push_status") as mock_change:
            update_system_diagnosis_push()
            # 未触发 push 更新
            mock_change.assert_not_called()
            # 应记录跳过日志
            self.mock_logger_celery_info.assert_any_call(
                f"[update_system_diagnosis_push] system {system.system_id} skip update"
            )

    def test_update_when_push_enabled(self):
        """
        场景2：系统开启了诊断推送，则应调用更新接口，传入True
        """
        System.objects.create(system_id="system_enabled", name="System Enabled", enable_system_diagnosis_push=True)
        # 模拟 handler.change_push_status 正常返回 True
        with mock.patch.object(SystemDiagnosisPushHandler, "change_push_status", return_value=True) as mock_change:
            update_system_diagnosis_push()
            # 应调用一次更新，参数为系统的状态 True
            mock_change.assert_called_once_with(True)

    def test_update_when_config_status_push(self):
        """
        场景3：系统未开启推送，但存在关联配置且状态为PUSH，此时也需要更新（以系统实际状态为准，参数为False）
        """
        system = System.objects.create(
            system_id="system_config_push", name="System Config Push", enable_system_diagnosis_push=False
        )
        # 创建关联的配置，push_status 为 PUSH
        SystemDiagnosisConfig.objects.create(
            system_id=system.system_id,
            push_uid="dummy_uid",
            push_status=SystemDiagnosisPushStatusEnum.PUSH.value,
        )
        with mock.patch.object(SystemDiagnosisPushHandler, "change_push_status", return_value=True) as mock_change:
            update_system_diagnosis_push()
            # 应调用一次更新，参数为系统当前的状态 False
            mock_change.assert_called_once_with(False)

    def test_exception_in_handler_does_not_propagate(self):
        """
        场景4：当 handler.change_push_status 调用时发生异常，定时任务应捕获异常并记录错误日志，而不向上抛出异常
        """
        system = System.objects.create(
            system_id="system_exception", name="System Exception", enable_system_diagnosis_push=True
        )
        with mock.patch.object(
            SystemDiagnosisPushHandler, "change_push_status", side_effect=Exception("Test exception")
        ) as mock_change:
            # 调用定时任务，异常会被 @ignored(Exception) 裁剪，不会传播
            update_system_diagnosis_push()
            mock_change.assert_called_once_with(True)
            # 应记录错误日志，日志内容中应包含系统ID及异常信息（这里不要求完全匹配）
            self.mock_logger_celery_error.assert_called()
            args, _ = self.mock_logger_celery_error.call_args
            self.assertIn(system.system_id, args[0])
            self.assertIn("Test exception", args[0])

    def test_mixed_scenarios(self):
        """
        场景5：混合多种系统数据
         - system1：未开启推送且无配置 → 应跳过更新
         - system2：开启推送 → 应更新，参数True
         - system3：未开启推送但存在配置且状态为PUSH → 应更新，参数False
        """
        system1 = System.objects.create(system_id="system1", name="System1", enable_system_diagnosis_push=False)
        System.objects.create(system_id="system2", name="System2", enable_system_diagnosis_push=True)
        system3 = System.objects.create(system_id="system3", name="System3", enable_system_diagnosis_push=False)
        SystemDiagnosisConfig.objects.create(
            system_id=system3.system_id,
            push_uid="dummy_uid",
            push_status=SystemDiagnosisPushStatusEnum.PUSH.value,
        )
        with mock.patch.object(SystemDiagnosisPushHandler, "change_push_status", return_value=True) as mock_change:
            update_system_diagnosis_push()
            # system2 和 system3 应该各调用一次更新
            self.assertEqual(mock_change.call_count, 2)
            calls = [mock.call(True), mock.call(False)]
            mock_change.assert_has_calls(calls, any_order=True)
            # system1 应跳过更新，跳过日志记录应存在
            self.mock_logger_celery_info.assert_any_call(
                f"[update_system_diagnosis_push] system {system1.system_id} skip update"
            )
