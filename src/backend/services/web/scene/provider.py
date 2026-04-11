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

from iam.resource.provider import ListResult
from iam.resource.utils import Page

from apps.permission.provider.base import IAMResourceProvider


class SceneResourceProvider(IAMResourceProvider):
    resource_type = "scene"
    resource_provider_serializer = None

    def list_attr_value_choices(self, attr: str, page: Page) -> List:
        return []

    def list_instance_by_policy(self, filters, page, **options):
        return ListResult(results=[], count=0)

    def filter_list_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], page: Page
    ) -> Tuple[List[dict], int]:
        try:
            from services.web.scene.models import Scene as SceneModel

            qs = SceneModel.objects.all().order_by("pk")
            scenes = qs[page.slice_from : page.slice_to]
            results = [{"id": str(s.pk), "display_name": s.name} for s in scenes]
            return results, qs.count()
        except ImportError:
            return [], 0

    def filter_fetch_instance_results(self, ids: List[str]) -> Tuple[List[dict], int]:
        try:
            from services.web.scene.models import Scene as SceneModel

            scenes = SceneModel.objects.filter(pk__in=ids)
            results = [{"id": str(s.pk), "display_name": s.name} for s in scenes]
            return results, scenes.count()
        except ImportError:
            return [], 0

    def filter_search_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], keyword: str, page: Page
    ) -> Tuple[List[dict], int]:
        try:
            from services.web.scene.models import Scene as SceneModel

            qs = SceneModel.objects.filter(name__icontains=keyword).order_by("pk")
            scenes = qs[page.slice_from : page.slice_to]
            results = [{"id": str(s.pk), "display_name": s.name} for s in scenes]
            return results, qs.count()
        except ImportError:
            return [], 0
