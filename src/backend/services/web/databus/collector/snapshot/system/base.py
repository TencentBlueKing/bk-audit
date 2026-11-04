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

from typing import Dict, List, Union

from django.conf import settings

from apps.itsm.constants import ITSM_V4_MIGRATION_MAP_KEY
from apps.meta.constants import GLOBAL_CONFIG_LEVEL_INSTANCE, ConfigLevelChoices
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
from services.web.risk.models import ProcessApplication


def _save_itsm_v4_migration_map(config_key: str, config_value: Union[Dict[str, str], List]) -> None:
    """
    持久化迁移映射：每解析出一个流程就落盘，保证进程中断后仍可恢复到同一个远端流程。
    """

    GlobalMetaConfig.set(
        config_key=config_key,  # ITSM_V4_MIGRATION_MAP_KEY,
        config_value=config_value,
        config_level=ConfigLevelChoices.GLOBAL.value,
        instance_key=GLOBAL_CONFIG_LEVEL_INSTANCE,
    )


def _load_itsm_v4_migration_map() -> Dict[str, str]:
    """
    读取持久化的「V3 服务标识 -> V4 workflow_key」迁移映射。

    该映射是重试幂等的唯一依据：本地已记录的服务直接复用原流程，
    不重新解析名称，因此不受远端返回内容变化的影响。
    """

    migration_map = GlobalMetaConfig.get(ITSM_V4_MIGRATION_MAP_KEY, default={}) or {}
    return migration_map if isinstance(migration_map, dict) else {}


def init_itsm_v4() -> bool:
    """
    从 GlobalMetaConfig 获取 service_id 与 workflow_key 的映射 migration_map
    再替换 ProcessApplication.approve_service_id
    migration_map 由人工在 itsm_4 上线前手动创建并保存到 GlobalMetaConfig，以确保万无一失
    """
    save_error = {}
    migration_map = _load_itsm_v4_migration_map()
    # migration_map 为空，表示是新环境或没有要迁移的内容，没有要创建的系统流程，返回True，使初始化成功
    if not migration_map:
        return True

    objs = ProcessApplication.objects.all()
    for obj in objs:
        try:
            workflow_key = migration_map.get(obj.approve_service_id, None)
            if workflow_key and workflow_key != obj.approve_service_id:
                obj.approve_service_id = workflow_key
                obj.save()
        except Exception as e:
            save_error[str(obj.approve_service_id)] = migration_map.get(obj.approve_service_id, None)
            print(str(e))
            continue
    if save_error:
        return False
    return True


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
