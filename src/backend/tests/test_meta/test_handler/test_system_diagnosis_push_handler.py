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
import json
from unittest import mock

from bk_resource import api
from bk_resource.exceptions import APIRequestError

from api.bk_vision.default import (
    CreateReportStrategy,
    DeleteReportStrategy,
    UpdateReportStrategy,
)
from apps.meta.constants import (
    SYSTEM_DIAGNOSIS_PUSH_TEMPLATE_KEY,
    ConfigLevelChoices,
    SystemDiagnosisPushStatusEnum,
)
from apps.meta.exceptions import SystemDiagnosisPushTemplateEmpty, SystemRoleMemberEmpty
from apps.meta.handlers.system_diagnosis import SystemDiagnosisPushHandler
from apps.meta.models import GlobalMetaConfig, System, SystemDiagnosisConfig, SystemRole
from services.web.risk.constants import SECURITY_PERSON_KEY
from tests.base import TestCase
from tests.test_meta.constants import (
    SYSTEM_DIAGNOSIS_PUSH_DISABLE,
    SYSTEM_DIAGNOSIS_PUSH_ENABLE,
    SYSTEM_DIAGNOSIS_PUSH_TEMPLATE,
)


class TestSystemDiagnosisPushHandler(TestCase):
    def setUp(self):
        # 创建测试系统
        self.system = System.objects.create(
            instance_id="test_system", name="Test System", enable_system_diagnosis_push=False
        )
        # 初始化handler前先准备测试数据
        self.prepare_test_data()
        # Mock Vision平台API
        self.mock_vision_apis()
        # 初始化handler
        self.handler = SystemDiagnosisPushHandler(system_id=self.system.system_id)

    def prepare_test_data(self):
        """准备测试所需的模型数据"""
        # 创建系统角色
        SystemRole.objects.create(system_id=self.system.system_id, role="admin", username="test_user")
        # 设置推送模板
        GlobalMetaConfig.set(
            config_key=SYSTEM_DIAGNOSIS_PUSH_TEMPLATE_KEY,
            config_value=SYSTEM_DIAGNOSIS_PUSH_TEMPLATE,
            config_level=ConfigLevelChoices.NAMESPACE,
            instance_key=self.system.namespace,
        )
        # SECURITY_PERSON_KEY
        GlobalMetaConfig.set(config_key=SECURITY_PERSON_KEY, config_value=["test_user"])

    def mock_vision_apis(self):
        """统一管理所有API mock"""
        # 策略创建/更新mock
        self.vision_create_mock = mock.patch.object(
            CreateReportStrategy,
            'perform_request',
            lambda self, push_params: {"uid": "test_uid", "status": push_params["status"]},
        ).start()

        self.vision_update_mock = mock.patch.object(
            UpdateReportStrategy,
            'perform_request',
            lambda self, push_params: {"uid": "test_uid", "status": push_params["status"]},
        ).start()

        # 策略删除mock
        self.vision_delete_mock = mock.patch.object(
            DeleteReportStrategy, 'perform_request', lambda self, push_params: {}
        ).start()

    def tearDown(self):
        mock.patch.stopall()

    def test_config_update_flow(self):
        """测试完整的配置更新流程"""
        # 开启推送
        self.assertTrue(self.handler.change_push_status(True))

        # 验证创建后的状态
        self.system.refresh_from_db()
        self.assertTrue(self.system.enable_system_diagnosis_push)
        config = SystemDiagnosisConfig.objects.get(system_id=self.system.system_id)
        self.assertEqual(config.push_uid, "test_uid")
        self.assertEqual(config.push_status, SystemDiagnosisPushStatusEnum.PUSH.value)
        self.assertEqual(config.push_config, SYSTEM_DIAGNOSIS_PUSH_ENABLE)

        # 关闭推送
        self.assertTrue(self.handler.change_push_status(False))

        # 验证更新后的状态
        self.system.refresh_from_db()
        self.assertFalse(self.system.enable_system_diagnosis_push)
        config.refresh_from_db()
        self.assertEqual(config.push_status, SystemDiagnosisPushStatusEnum.PAUSE.value)
        self.assertEqual(config.push_config, SYSTEM_DIAGNOSIS_PUSH_DISABLE)

        # 删除推送
        self.handler.delete_push()

        # 验证删除后的状态
        self.system.refresh_from_db()
        self.assertFalse(self.system.enable_system_diagnosis_push)
        with self.assertRaises(SystemDiagnosisConfig.DoesNotExist):
            config.refresh_from_db()

    def test_transaction_atomicity(self):
        """测试事务原子性-当API调用失败时数据库状态一致性"""
        with mock.patch.object(api.bk_vision, 'create_report_strategy', side_effect=APIRequestError()):
            self.handler.change_push_status(True)
            self.assertEqual(self.system.enable_system_diagnosis_push, False)
            config: SystemDiagnosisConfig = SystemDiagnosisConfig.objects.first()
            self.assertIsNotNone(config.push_error_message)
            self.assertEqual(config.push_status, SystemDiagnosisPushStatusEnum.FAILED.value)

        # 开启
        self.assertTrue(self.handler.change_push_status(True))

        # 关闭失败
        with mock.patch.object(api.bk_vision, 'update_report_strategy', side_effect=APIRequestError()):
            self.system.refresh_from_db()
            self.handler.change_push_status(False)
            self.assertEqual(self.system.enable_system_diagnosis_push, True)
            config: SystemDiagnosisConfig = SystemDiagnosisConfig.objects.first()
            self.assertIsNotNone(config.push_error_message)
            self.assertEqual(config.push_status, SystemDiagnosisPushStatusEnum.FAILED.value)

        # 关闭
        self.assertTrue(self.handler.change_push_status(False))

        # 开启失败
        with mock.patch.object(api.bk_vision, 'update_report_strategy', side_effect=APIRequestError()):
            self.system.refresh_from_db()
            self.handler.change_push_status(True)
            self.assertEqual(self.system.enable_system_diagnosis_push, False)
            config: SystemDiagnosisConfig = SystemDiagnosisConfig.objects.first()
            self.assertIsNotNone(config.push_error_message)
            self.assertEqual(config.push_status, SystemDiagnosisPushStatusEnum.FAILED.value)

    def test_template_rendering_edge_cases(self):
        """测试模板渲染边界情况"""
        # 测试空收件人场景
        SystemRole.objects.filter(system_id=self.system.system_id).delete()
        with mock.patch("apps.meta.handlers.system_diagnosis.is_product", return_value=True):
            with self.assertRaises(SystemRoleMemberEmpty):
                self.handler.push_config

    def test_invalid_template_handling(self):
        # 测试无效JSON模板
        GlobalMetaConfig.set(
            config_key=SYSTEM_DIAGNOSIS_PUSH_TEMPLATE_KEY,
            config_value="invalid{json",
            config_level=ConfigLevelChoices.NAMESPACE,
            instance_key=self.system.namespace,
        )
        self.handler = SystemDiagnosisPushHandler(system_id=self.system.system_id)
        with self.assertRaises(json.JSONDecodeError):
            self.handler.push_config

        GlobalMetaConfig.objects.filter(config_key=SYSTEM_DIAGNOSIS_PUSH_TEMPLATE_KEY).delete()
        self.handler = SystemDiagnosisPushHandler(system_id=self.system.system_id)
        with self.assertRaises(SystemDiagnosisPushTemplateEmpty):
            self.handler.push_config

    def test_push_deletion_failure_handling(self):
        """测试删除推送时的异常处理"""
        # 准备测试数据
        SystemDiagnosisConfig.objects.create(
            system_id=self.system.system_id, push_uid="test_uid", push_status=SystemDiagnosisPushStatusEnum.PUSH.value
        )

        # 模拟API调用失败
        with mock.patch.object(api.bk_vision, 'delete_report_strategy', side_effect=APIRequestError()):
            with self.assertRaises(APIRequestError):
                self.handler.delete_push()

    def test_system_data_composition(self):
        """测试系统数据生成逻辑"""
        # 生产环境数据
        prod_data = self.handler.system_data
        self.assertEqual(prod_data["recipient"], ["test_user"])

        # 开发环境数据
        dev_data = self.handler.system_data
        self.assertEqual(dev_data["recipient"], GlobalMetaConfig.get(config_key=SECURITY_PERSON_KEY))
