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

from typing import List, Optional, Tuple

from iam import PathEqDjangoQuerySetConverter
from iam.resource.provider import ListResult
from iam.resource.utils import Page

from apps.permission.handlers.resource_types import ResourceEnum
from apps.permission.provider.base import IAMResourceProvider
from services.web.risk.models import ProcessApplication
from services.web.scene.constants import ResourceVisibilityType
from services.web.scene.models import ResourceBindingScene


class ProcessApplicationResourceProvider(IAMResourceProvider):
    resource_type = "process_application"
    resource_provider_serializer = None

    def list_attr_value_choices(self, attr: str, page: Page) -> List:
        return []

    def list_instance_by_policy(self, filters, page, **options):
        expression = filters.expression
        if not expression:
            return ListResult(results=[], count=0)

        key_mapping = {f"{self.resource_type}.id": "id"}
        converter = PathEqDjangoQuerySetConverter(key_mapping)
        django_filters = converter.convert(expression)
        queryset = ProcessApplication.objects.filter(django_filters).order_by("id")
        results = [
            {"id": str(item.id), "display_name": item.name} for item in queryset[page.slice_from : page.slice_to]
        ]
        return ListResult(results=results, count=queryset.count())

    def filter_list_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], page: Page
    ) -> Tuple[List[dict], int]:
        qs = ProcessApplication.objects.all().order_by("id")
        if parent_id and resource_type == ResourceEnum.SCENE.id:
            bound_ids = ResourceBindingScene.objects.filter(
                binding__resource_type=ResourceVisibilityType.PROCESS_APPLICATION,
                scene_id=parent_id,
            ).values_list("binding__resource_id", flat=True)
            qs = ProcessApplication.objects.filter(id__in=bound_ids).order_by("id")
        results = [{"id": str(item.id), "display_name": item.name} for item in qs[page.slice_from : page.slice_to]]
        return results, qs.count()

    def filter_fetch_instance_results(self, ids: List[str]) -> Tuple[List[dict], int]:
        qs = ProcessApplication.objects.filter(id__in=ids)
        results = [{"id": str(item.id), "display_name": item.name} for item in qs]
        return results, qs.count()

    def filter_search_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], keyword: str, page: Page
    ) -> Tuple[List[dict], int]:
        qs = ProcessApplication.objects.filter(name__icontains=keyword).order_by("id")
        if parent_id and resource_type == ResourceEnum.SCENE.id:
            bound_ids = ResourceBindingScene.objects.filter(
                binding__resource_type=ResourceVisibilityType.PROCESS_APPLICATION,
                scene_id=parent_id,
            ).values_list("binding__resource_id", flat=True)
            qs = qs.filter(id__in=bound_ids)
        results = [{"id": str(item.id), "display_name": item.name} for item in qs[page.slice_from : page.slice_to]]
        return results, qs.count()
