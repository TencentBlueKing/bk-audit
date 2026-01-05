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

from unittest import mock

from core.utils.data import ordered_dict_to_json
from services.web.databus.models import StorageOperateLog
from services.web.databus.storage.serializers import StorageCustomOptionSerializer
from tests.base import TestCase
from tests.test_databus.collector_plugin.constants import (
    CREATE_PLUGIN_DATA as CREATE_PLUGIN_API_RESP,
)
from tests.test_databus.storage.constants import (
    CLUSTER_ID,
    CREATE_OR_UPDATE_REDIS_DATA,
    CREATE_OR_UPDATE_REDIS_PARAMS,
    CREATE_REPLICA_STORAGE_PARAMS,
    CREATE_STORAGE_PARAMS,
    GET_STORAGES_API_RESP,
    REPLICA_STORAGE_ACTIVATE_PARAMS,
    REPLICA_WRITE_CLUSTER_ID,
    STORAGE_ACTIVATE_PARAMS,
    STORAGE_LIST_DATA,
    STORAGE_LIST_PARAMS,
    STORAGE_OPERATE_LOG_DATA,
)


class StorageTest(TestCase):
    def setUp(self) -> None:
        self.storage_operate_log = StorageOperateLog.objects.create(**STORAGE_OPERATE_LOG_DATA)

    @mock.patch("databus.storage.resources.cache.get", mock.Mock(return_value=None))
    def test_storage_activate(self):
        """StorageActivateResource"""
        result = self.resource.databus.storage.storage_activate(**STORAGE_ACTIVATE_PARAMS)
        self.assertEqual(int(result), STORAGE_ACTIVATE_PARAMS["cluster_id"])

    @mock.patch("databus.storage.resources.cache.get", mock.Mock(return_value=None))
    def test_replica_storage_activate(self):
        """StorageActivateResource"""
        result = self.resource.databus.storage.storage_activate(**REPLICA_STORAGE_ACTIVATE_PARAMS)
        self.assertEqual(int(result), REPLICA_STORAGE_ACTIVATE_PARAMS["cluster_id"])

    @mock.patch("databus.storage.resources.api.bk_log.get_storages", mock.Mock(return_value=GET_STORAGES_API_RESP))
    def test_storage_list(self):
        """StorageListResource"""
        StorageOperateLog.objects.all().update(operate_at=self.storage_operate_log.operate_at)
        result = self.resource.databus.storage.storage_list(**STORAGE_LIST_PARAMS)
        result = ordered_dict_to_json(result)
        self.assertEqual(result, STORAGE_LIST_DATA)

    @mock.patch("databus.storage.resources.cache.get", mock.Mock(return_value=None))
    @mock.patch(
        "databus.storage.resources.resource.databus.collector_plugin.create_plugin",
        mock.Mock(return_value=CREATE_PLUGIN_API_RESP),
    )
    @mock.patch("databus.storage.resources.api.bk_log.create_storage", mock.Mock(return_value=CLUSTER_ID))
    def test_create_storage(self):
        """CreateStorageResource"""
        result = self.resource.databus.storage.create_storage(**CREATE_STORAGE_PARAMS)
        self.assertEqual(result, CLUSTER_ID)

    @mock.patch("databus.storage.resources.cache.get", mock.Mock(return_value=None))
    @mock.patch(
        "databus.storage.resources.resource.databus.collector_plugin.create_plugin",
        mock.Mock(return_value=CREATE_PLUGIN_API_RESP),
    )
    @mock.patch("databus.storage.resources.api.bk_log.create_storage", mock.Mock(return_value=REPLICA_WRITE_CLUSTER_ID))
    def test_create_replica_storage(self):
        """CreateStorageResource"""
        result = self.resource.databus.storage.create_storage(**CREATE_REPLICA_STORAGE_PARAMS)
        self.assertEqual(result, REPLICA_WRITE_CLUSTER_ID)

    @mock.patch("databus.storage.handler.redis.api.bk_base.create_resource_set", mock.Mock(return_value={}))
    def test_create_or_update_redis(self):
        """CreateOrUpdateRedisResource"""
        result = self.resource.databus.storage.create_or_update_redis(**CREATE_OR_UPDATE_REDIS_PARAMS)
        result = ordered_dict_to_json(result)
        result.pop("redis_id", None)
        result.pop("is_deleted", None)
        self.assertEqual(result, CREATE_OR_UPDATE_REDIS_DATA)

    def test_admin_with_empty_string(self):
        """
        测试 admin 字段包含空字符串的情况
        根据日志: "admin": ["admin", ""] - 包含一个空字符串
        """
        # 模拟日志中返回的数据格式
        test_data = {
            "bk_biz_id": 19069,
            "hot_warm_config": {
                "is_enabled": False,
                "hot_attr_name": "",
                "hot_attr_value": "",
                "warm_attr_name": "",
                "warm_attr_value": "",
            },
            "source_type": "other",
            "visible_config": {"visible_type": "current_biz", "visible_bk_biz": [], "bk_biz_labels": {}},
            "setup_config": {
                "retention_days_default": 30,
                "number_of_replicas_default": 1,
                "retention_days_max": 30,
                "number_of_replicas_max": 1,
                "es_shards_default": 3,
                "es_shards_max": 512,
            },
            "admin": ["admin", ""],
            "description": "审计中心存储集群",
        }

        serializer = StorageCustomOptionSerializer(data=test_data)
        if serializer.is_valid():
            print(f"admin 字段值: {serializer.validated_data.get('admin')}")
        else:
            print("验证失败!")
            print(f"错误信息: {serializer.errors}")

        self.assertTrue(serializer.is_valid(), f"序列化验证失败: {serializer.errors}")
        self.assertEqual(serializer.validated_data.get('admin'), ["admin", ""])

        return serializer.is_valid()
