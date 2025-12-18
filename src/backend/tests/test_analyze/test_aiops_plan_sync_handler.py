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
from unittest.mock import patch

from django.test import TestCase

from services.web.analyze.controls.aiops import AiopsPlanSyncHandler
from services.web.analyze.models import Control, ControlTypeChoices, ControlVersion


class TestAiopsPlanSyncHandler(TestCase):
    def setUp(self):
        self.handler = AiopsPlanSyncHandler()

    @patch("services.web.analyze.controls.aiops.api.bk_base.get_scene_plans")
    @patch("services.web.analyze.controls.aiops.api.bk_base.get_plan_detail")
    def test_restore_soft_deleted_versions_and_create_new(self, mock_get_plan_detail, mock_get_scene_plans):
        """
        控件版本被软删除，远端新增 V3 → 本地应恢复所有旧版本 + 创建 V3
        """
        control_name = "软删除控件多版本"
        control = Control._objects.create(
            control_name=control_name,
            control_type_id=ControlTypeChoices.AIOPS.value,
            is_deleted=True,
        )
        for version_no, version_id in [(1, 111), (2, 222)]:
            ControlVersion._objects.create(
                control_id=control.control_id,
                control_version=version_no,
                is_deleted=True,
                input_config={},
                output_config={},
                variable_config={},
                extra_config={"plan_id": 500, "latest_plan_version_id": version_id},
            )

        mock_get_scene_plans.return_value = [
            {"plan_id": 500, "status": "published", "plan_alias": control_name, "version_no": "V3"}
        ]
        mock_get_plan_detail.return_value = {
            "plan_id": 500,
            "plan_alias": control_name,
            "latest_plan_version_id": 333,
            "version_no": "V3",
            "io_info": {
                "input_config": {"param": "value3"},
                "output_config": {"result": "value3"},
            },
            "variable_info": {"var": "val3"},
        }

        self.handler.sync()

        control.refresh_from_db()
        self.assertFalse(control.is_deleted)

        versions = ControlVersion.objects.filter(control_id=control.control_id).order_by("control_version")
        self.assertEqual(versions.count(), 3)
        for v in versions:
            self.assertFalse(v.is_deleted)
        self.assertEqual(versions.get(control_version=3).input_config, {"param": "value3"})

    @patch("services.web.analyze.controls.aiops.api.bk_base.get_scene_plans")
    def test_delete_control_when_remote_missing(self, mock_get_scene_plans):
        """
        控件在本地存在，但远端不存在，应被物理删除
        """
        control = Control.objects.create(
            control_name="远端不存在控件",
            control_type_id=ControlTypeChoices.AIOPS.value,
            is_deleted=True,
        )
        ControlVersion.objects.create(
            control_id=control.control_id,
            control_version=1,
            is_deleted=True,
            extra_config={"plan_id": 999, "latest_plan_version_id": 123},
            input_config={},
            output_config={},
            variable_config={},
        )
        mock_get_scene_plans.return_value = []

        self.handler.sync()

        self.assertFalse(Control.objects.filter(control_id=control.control_id).exists())
        self.assertFalse(ControlVersion.objects.filter(control_id=control.control_id).exists())

    @patch("services.web.analyze.controls.aiops.api.bk_base.get_scene_plans")
    @patch("services.web.analyze.controls.aiops.api.bk_base.get_plan_detail")
    def test_skip_when_version_is_up_to_date(self, mock_get_plan_detail, mock_get_scene_plans):
        """
        控件版本已是最新，跳过不处理
        """
        control_name = "不需要更新控件"
        control = Control.objects.create(
            control_name=control_name,
            control_type_id=ControlTypeChoices.AIOPS.value,
        )
        ControlVersion.objects.create(
            control_id=control.control_id,
            control_version=1,
            extra_config={"plan_id": 123, "latest_plan_version_id": 999},
            input_config={"p": "v"},
            output_config={},
            variable_config={},
        )

        mock_get_scene_plans.return_value = [
            {"plan_id": 123, "status": "published", "plan_alias": control_name, "version_no": "V1"}
        ]
        mock_get_plan_detail.return_value = {
            "plan_id": 123,
            "plan_alias": control_name,
            "latest_plan_version_id": 999,
            "version_no": "V1",
            "io_info": {"input_config": {"p": "v"}, "output_config": {}},
            "variable_info": {},
        }

        with patch.object(self.handler, "create_control_and_control_version") as mock_create:
            self.handler.sync()
            mock_create.assert_not_called()
