# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from datetime import timedelta
from types import SimpleNamespace

from django.utils import timezone
from iam.resource.utils import Page

from apps.meta.models import Tag
from services.web.strategy_v2.models import Strategy, StrategyTag, StrategyTagSyncTrash
from services.web.strategy_v2.provider import StrategyTagResourceProvider
from tests.base import TestCase


class StrategyTagProviderTest(TestCase):
    def setUp(self) -> None:  # NOCC:invalid-name(单元测试)
        super().setUp()
        self.provider = StrategyTagResourceProvider()
        self.strategy = Strategy.objects.create(namespace="default", strategy_name="strategy-one")
        self.tag_deleted = Tag.objects.create(tag_name="tag-to-delete")
        self.tag_live = Tag.objects.create(tag_name="tag-live")

    def _build_filter(self) -> SimpleNamespace:
        now = timezone.now()
        return SimpleNamespace(
            start_time=int((now - timedelta(minutes=5)).timestamp() * 1000),
            end_time=int((now + timedelta(minutes=5)).timestamp() * 1000),
        )

    def test_fetch_instance_list_includes_trash_records(self):
        deleted_relation = StrategyTag.objects.create(strategy=self.strategy, tag=self.tag_deleted)
        live_relation = StrategyTag.objects.create(strategy=self.strategy, tag=self.tag_live)

        filter_obj = self._build_filter()
        page = Page(limit=10, offset=0)

        initial_result = self.provider.fetch_instance_list(filter_obj, page)
        self.assertEqual(initial_result.count, 2)
        self.assertEqual(initial_result.results[0]["data"]["tag_id"], live_relation.tag_id)

        deleted_relation_id = deleted_relation.id
        deleted_relation.delete()

        tombstone = StrategyTagSyncTrash.objects.get(original_id=deleted_relation_id)
        self.assertEqual(tombstone.strategy_id, self.strategy.strategy_id)
        self.assertEqual(tombstone.tag_id, self.tag_deleted.tag_id)

        refreshed_result = self.provider.fetch_instance_list(self._build_filter(), page)
        self.assertEqual(refreshed_result.count, 2)

        live_entry = refreshed_result.results[0]
        tombstone_entry = refreshed_result.results[1]

        self.assertEqual(live_entry["id"], str(live_relation.id))
        self.assertEqual(live_entry["data"]["tag_id"], live_relation.tag_id)
        self.assertEqual(live_entry["data"]["strategy_id"], self.strategy.strategy_id)

        self.assertEqual(tombstone_entry["id"], str(deleted_relation_id))
        self.assertEqual(tombstone_entry["data"]["tag_id"], 0)
        self.assertEqual(tombstone_entry["data"]["strategy_id"], 0)
