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

import datetime
from typing import List, Optional, Tuple

from iam import PathEqDjangoQuerySetConverter
from iam.resource.provider import ListResult, SchemaResult
from iam.resource.utils import Page

from apps.permission.provider.base import IAMResourceProvider
from core.serializers import get_serializer_fields
from services.web.scene.serializers import SceneSimpleListSerializer


class SceneResourceProvider(IAMResourceProvider):
    resource_type = "scene"
    resource_provider_serializer = SceneSimpleListSerializer

    def list_attr_value_choices(self, attr: str, page: Page) -> List:
        return []

    def list_instance_by_policy(self, filters, page, **options):
        expression = filters.expression
        if not expression:
            return ListResult(results=[], count=0)

        from services.web.scene.models import Scene as SceneModel

        key_mapping = {
            f"{self.resource_type}.id": "scene_id",
        }
        converter = PathEqDjangoQuerySetConverter(key_mapping)
        django_filters = converter.convert(expression)
        queryset = SceneModel.objects.filter(django_filters).order_by("pk")
        scenes = queryset[page.slice_from : page.slice_to]
        results = [{"id": str(scene.scene_id), "display_name": scene.name} for scene in scenes]
        return ListResult(results=results, count=queryset.count())

    def filter_list_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], page: Page
    ) -> Tuple[List[dict], int]:
        try:
            from services.web.scene.models import Scene as SceneModel

            qs = SceneModel.objects.all().order_by("pk")
            scenes = qs[page.slice_from : page.slice_to]
            results = [{"id": str(s.scene_id), "display_name": s.name} for s in scenes]
            return results, qs.count()
        except ImportError:
            return [], 0

    def filter_fetch_instance_results(self, ids: List[str]) -> Tuple[List[dict], int]:
        try:
            from services.web.scene.models import Scene as SceneModel

            scenes = SceneModel.objects.filter(scene_id__in=ids)
            results = [{"id": str(s.scene_id), "display_name": s.name} for s in scenes]
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
            results = [{"id": str(s.scene_id), "display_name": s.name} for s in scenes]
            return results, qs.count()
        except ImportError:
            return [], 0

    def fetch_instance_list(self, filters, page, **options):
        from services.web.scene.models import Scene as SceneModel

        start_time = datetime.datetime.fromtimestamp(int(filters.start_time // 1000))
        end_time = datetime.datetime.fromtimestamp(int(filters.end_time // 1000))
        queryset = SceneModel._base_manager.filter(updated_at__gt=start_time, updated_at__lte=end_time).order_by("pk")
        results = []
        for scene in queryset[page.slice_from : page.slice_to]:
            data = SceneSimpleListSerializer(instance=scene).data
            data["is_deleted"] = scene.is_deleted
            results.append(
                {
                    "id": str(scene.scene_id),
                    "display_name": scene.name,
                    "is_deleted": scene.is_deleted,
                    "creator": scene.created_by,
                    "created_at": int(scene.created_at.timestamp() * 1000) if scene.created_at else None,
                    "updater": scene.updated_by,
                    "updated_at": int(scene.updated_at.timestamp() * 1000) if scene.updated_at else None,
                    "data": data,
                }
            )
        return ListResult(results=results, count=queryset.count())

    def fetch_resource_type_schema(self, **options):
        data = get_serializer_fields(SceneSimpleListSerializer)
        properties = {
            item["name"]: {
                "type": item["type"].lower(),
                "description_en": item["name"],
                "description": item["description"],
            }
            for item in data
        }
        properties.setdefault(
            "scene_id",
            {
                "type": "integer",
                "description_en": "scene_id",
                "description": "场景ID",
            },
        )
        properties.setdefault(
            "is_deleted",
            {
                "type": "boolean",
                "description_en": "is_deleted",
                "description": "是否删除",
            },
        )
        return SchemaResult(properties=properties)
