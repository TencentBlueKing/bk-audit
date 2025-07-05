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
from django.test import TestCase

from services.web.analyze.controls.aiops import AiopsPlanSyncHandler
from services.web.analyze.models import Control, ControlTypeChoices


class TestAiopsPlanSyncHandler(TestCase):
    def setUp(self):
        # 预先创建一个软删除的 Control，名字和后面测试用的相同
        self.control_name = "测试控件名"
        self.soft_deleted_control = Control._objects.create(
            control_name=self.control_name,
            control_type_id=ControlTypeChoices.AIOPS.value,
            is_deleted=True,
        )
        self.handler = AiopsPlanSyncHandler()

    def test_create_or_update_control_restores_soft_deleted(self):
        # 传入 soft_deleted_control 的名字，模拟“创建”流程
        control = self.handler.create_or_update_control(control_name=self.control_name)
        self.assertIsNotNone(control)
        self.assertEqual(control.control_name, self.control_name)
        # 验证原本软删除的 control 被恢复
        self.assertFalse(control.is_deleted)
        self.assertEqual(control.control_id, self.soft_deleted_control.control_id)

    def test_create_or_update_control_creates_new_if_not_exists(self):
        new_name = "全新控件名"
        control = self.handler.create_or_update_control(control_name=new_name)
        self.assertIsNotNone(control)
        self.assertEqual(control.control_name, new_name)
        self.assertFalse(control.is_deleted)
        # 验证数据库确实有了这个新控件
        db_control = Control.objects.filter(
            control_name=new_name, control_type_id=ControlTypeChoices.AIOPS.value
        ).first()
        self.assertIsNotNone(db_control)
        self.assertEqual(db_control.control_id, control.control_id)
