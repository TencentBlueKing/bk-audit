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

from django.conf import settings
from django.utils.translation import gettext
from iam import Resource
from iam.eval.constants import KEYWORD_BK_IAM_PATH

from apps.permission.handlers.resource_types.base import ResourceTypeMeta
from services.web.scene.constants import ResourceVisibilityType
from services.web.scene.models import ResourceBindingScene


class Rule(ResourceTypeMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "rule"
    name = gettext("处理规则")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "rule"}]

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        from services.web.risk.models import RiskRule as RuleModel

        resource = cls.create_simple_instance(instance_id, attribute)
        instance_name = str(instance_id)
        rule = RuleModel.objects.filter(pk=instance_id).first()
        if rule:
            instance_name = rule.name

        # 通过 ResourceBindingScene 反查 scene_id（业务模型已移除 scene_id 字段）
        scene_id = (
            ResourceBindingScene.objects.filter(
                binding__resource_type=ResourceVisibilityType.RISK_RULE,
                binding__resource_id=str(instance_id),
            )
            .values_list("scene_id", flat=True)
            .first()
        )
        scene_id = str(scene_id) if scene_id else ""

        resource.attribute = {
            "id": str(instance_id),
            "name": instance_name,
            KEYWORD_BK_IAM_PATH: f"/scene,{scene_id}/rule,{instance_id}/",
        }
        return resource
