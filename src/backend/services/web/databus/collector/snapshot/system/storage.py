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

from bk_resource import api
from django.conf import settings

from services.web.databus.collector.snapshot.system.clean import PullCleanHandler
from services.web.databus.storage.handler.redis import RedisHandler


class PullStorageHandler:
    def __init__(self, bkbase_data_id, config_name, resource_type=None):
        self.bkbase_data_id = bkbase_data_id
        self.config_name = config_name
        self.resource_type = resource_type

    @property
    def config(self):
        # 字段
        fields = PullCleanHandler.get_fields(self.resource_type)
        for field in fields:
            field["physical_field"] = field["field_name"]
        # 配置
        return {
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "raw_data_id": self.bkbase_data_id,
            "data_type": "clean",
            "result_table_name": self.config_name,
            "result_table_name_alias": self.config_name,
            "storage_type": "redis",
            "storage_cluster": RedisHandler.pick_redis(settings.APP_CODE).redis_name_en,
            "expires": "-1",
            "fields": fields,
        }

    def create_storage(self):
        print(f"[HttpPull] Params => {self.config}")
        return api.bk_base.databus_storages_post(self.config)
