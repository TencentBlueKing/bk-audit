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

from apps.meta.models import GlobalMetaConfig
from services.web.databus.collector.snapshot.system.clean import PullCleanHandler
from services.web.databus.collector.snapshot.system.pull import HttpPullHandler
from services.web.databus.collector.snapshot.system.storage import PullStorageHandler
from services.web.databus.constants import (
    ACTION_DATA_CONFIG_KEY,
    ACTION_DATA_RT_KEY,
    RESOURCE_TYPE_DATA_CONFIG_KEY,
    RESOURCE_TYPE_DATA_RT_KEY,
    USER_INFO_DATA_CONFIG_KEY,
    USER_INFO_DATA_RT_KEY,
)


def create_iam_data_link(resource_type):
    if resource_type == "resource_type":
        config_key = RESOURCE_TYPE_DATA_CONFIG_KEY
        rt_key = RESOURCE_TYPE_DATA_RT_KEY
    elif resource_type == "action":
        config_key = ACTION_DATA_CONFIG_KEY
        rt_key = ACTION_DATA_RT_KEY
    elif resource_type == "user":
        config_key = USER_INFO_DATA_CONFIG_KEY
        rt_key = USER_INFO_DATA_RT_KEY
    else:
        raise Exception(f"ResourceType Does Not Support => {resource_type}")
    print(f"[CreateIAMDataLink] ConfigKey => {config_key}; RTKey => {rt_key}")
    config_name, bkbase_data_id = HttpPullHandler(resource_type).create_data_id()
    print(f"[CreateIAMDataLink] ConfigName => {config_name}; DataID => {bkbase_data_id}")
    clean_resp = PullCleanHandler(bkbase_data_id, config_name, resource_type).create_clean()
    storage_resp = PullStorageHandler(bkbase_data_id, config_name, resource_type).create_storage()
    GlobalMetaConfig.set(
        config_key,
        {
            "config_name": config_name,
            "bkbase_data_id": bkbase_data_id,
            "clean_resp": clean_resp,
            "storage_resp": storage_resp,
        },
    )
    GlobalMetaConfig.set(rt_key, f"{settings.DEFAULT_BK_BIZ_ID}_{config_name}")
