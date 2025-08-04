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

from apps.meta.exceptions import EnumMappingRelationInvalid
from apps.meta.models import (
    EnumMappingCollection,
    EnumMappingCollectionRelation,
    EnumMappingEntity,
)
from tests.base import TestCase


class EnumMappingResourceTest(TestCase):
    def setUp(self):
        self.collection_id = "test_collection"
        self.mappings = [
            {"key": "1", "name": "one"},
            {"key": "2", "name": "two"},
        ]
        self.related_type = "strategy"
        self.related_object_id = 1

    def test_batch_update_enum_mappings(self):
        params = {
            "collection_id": self.collection_id,
            "mappings": self.mappings,
            "related_type": self.related_type,
            "related_object_id": self.related_object_id,
        }
        result = self.resource.meta.batch_update_enum_mappings(**params)
        self.assertEqual(result, "success")
        self.assertTrue(EnumMappingCollection.objects.filter(collection_id=self.collection_id).exists())
        self.assertEqual(
            EnumMappingEntity.objects.filter(collection__collection_id=self.collection_id).count(),
            len(self.mappings),
        )
        self.assertTrue(
            EnumMappingCollectionRelation.objects.filter(
                collection_id=self.collection_id,
                related_type=self.related_type,
                related_object_id=str(self.related_object_id),
            ).exists()
        )

        params["mappings"] = []
        result = self.resource.meta.batch_update_enum_mappings(**params)
        self.assertEqual(result, "success")
        self.assertFalse(EnumMappingCollection.objects.filter(collection_id=self.collection_id).exists())
        self.assertFalse(
            EnumMappingCollectionRelation.objects.filter(
                collection_id=self.collection_id,
                related_type=self.related_type,
                related_object_id=str(self.related_object_id),
            ).exists()
        )

    def test_get_enum_mappings_relation(self):
        self.resource.meta.batch_update_enum_mappings(
            collection_id=self.collection_id,
            mappings=self.mappings,
            related_type=self.related_type,
            related_object_id=self.related_object_id,
        )
        result = self.resource.meta.get_enum_mappings_relation(
            related_type=self.related_type,
            related_object_id=self.related_object_id,
        )
        self.assertEqual(result, [self.collection_id])

    def test_get_enum_mapping_by_collection_keys(self):
        self.resource.meta.batch_update_enum_mappings(
            collection_id=self.collection_id,
            mappings=self.mappings,
            related_type=self.related_type,
            related_object_id=self.related_object_id,
        )
        params = {
            "collection_keys": [
                {"collection_id": self.collection_id, "key": "1"},
                {"collection_id": self.collection_id, "key": "2"},
            ],
            "related_type": self.related_type,
            "related_object_id": self.related_object_id,
        }
        result = self.resource.meta.get_enum_mapping_by_collection_keys(**params)
        result = sorted(result, key=lambda x: x["key"])
        expected = [
            {"collection_id": self.collection_id, "key": "1", "name": "one"},
            {"collection_id": self.collection_id, "key": "2", "name": "two"},
        ]
        self.assertEqual(result, expected)

    def test_get_enum_mapping_by_collection_keys_relation_invalid(self):
        self.resource.meta.batch_update_enum_mappings(
            collection_id=self.collection_id,
            mappings=self.mappings,
            related_type=self.related_type,
            related_object_id=self.related_object_id,
        )
        params = {
            "collection_keys": [{"collection_id": self.collection_id, "key": "1"}],
            "related_type": self.related_type,
            "related_object_id": 2,
        }
        with self.assertRaises(EnumMappingRelationInvalid):
            self.resource.meta.get_enum_mapping_by_collection_keys(**params)

    def test_get_enum_mapping_by_collection(self):
        self.resource.meta.batch_update_enum_mappings(
            collection_id=self.collection_id,
            mappings=self.mappings,
            related_type=self.related_type,
            related_object_id=self.related_object_id,
        )
        params = {
            "collection_id": self.collection_id,
            "related_type": self.related_type,
            "related_object_id": self.related_object_id,
        }
        result = self.resource.meta.get_enum_mapping_by_collection(**params)
        result = sorted(result, key=lambda x: x["key"])
        expected = [
            {"collection_id": self.collection_id, "key": "1", "name": "one"},
            {"collection_id": self.collection_id, "key": "2", "name": "two"},
        ]
        self.assertEqual(result, expected)

    def test_get_enum_mapping_by_collection_relation_invalid(self):
        self.resource.meta.batch_update_enum_mappings(
            collection_id=self.collection_id,
            mappings=self.mappings,
            related_type=self.related_type,
            related_object_id=self.related_object_id,
        )
        params = {
            "collection_id": self.collection_id,
            "related_type": self.related_type,
            "related_object_id": 2,
        }
        with self.assertRaises(EnumMappingRelationInvalid):
            self.resource.meta.get_enum_mapping_by_collection(**params)
