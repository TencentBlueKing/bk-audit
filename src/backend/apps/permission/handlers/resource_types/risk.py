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
from typing import List

from django.conf import settings
from django.utils.translation import gettext
from iam import Resource
from iam.eval.constants import KEYWORD_BK_IAM_PATH

from apps.permission.handlers.resource_types import ResourceTypeMeta

from .strategy import Strategy


class Risk(ResourceTypeMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "risk"
    name = gettext("风险")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "risk"}]

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        return cls.batch_create_instance([instance_id], attribute)[0][0]

    @classmethod
    def batch_create_instance(cls, instance_ids, attribute=None) -> List[List[Resource]]:
        from services.web.risk.models import Risk

        risks = Risk.objects.filter(risk_id__in=instance_ids).distinct().order_by().only("risk_id", "strategy_id")
        risk_map = {risk.risk_id: risk for risk in risks}
        resources = []
        for instance_id in instance_ids:
            resource = cls.create_simple_instance(instance_id, attribute)
            instance_name = instance_id
            strategy_id = 0
            risk = risk_map.get(instance_id)
            if risk:
                instance_name = risk.risk_id
                strategy_id = risk.strategy_id
            resource.attribute = {
                "id": str(resource.id),
                "name": instance_name,
                KEYWORD_BK_IAM_PATH: f"/{Strategy.id},{strategy_id}/",
            }
            resources.append([resource])
        return resources
