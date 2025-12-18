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

from bk_resource import resource
from django.db.models import QuerySet

from apps.meta.constants import SystemAuditStatusEnum, SystemStageEnum, SystemStatusEnum
from apps.meta.models import System
from services.web.databus.constants import (
    LogReportStatus,
    SnapshotReportStatus,
    SnapshotStatusDict,
    SystemStatusDetailEnum,
    SystemStatusDict,
    TailLogStatusDict,
)


def fetch_system_status(namespace: str, system_ids: List[str]) -> Dict[str, SystemStatusDict]:
    """
    获取系统状态信息
    1. 系统未接入审计中心: 未接入
    2.  系统已接入审计状态
        1. 没有权限模型 or 没有日志上报 or 没有配置资产上报: 待完善
        2. 资产上报异常 or 日志上报无数据: 数据异常
        3. 否则：系统接入 & 有权限模型 & 日志上报正常 & 资产上报： 数据正常
    """

    if not system_ids:
        return {}

    # 排序复用缓存
    system_ids = sorted(system_ids)

    # 1. 获取系统审计状态
    systems: QuerySet = (
        System.objects.with_action_resource_type_count()
        .filter(
            namespace=namespace,
            system_id__in=system_ids,
        )
        .values("system_id", "audit_status", "action_count", "resource_type_count")
    )

    # 2. 获取日志上报信息
    system_ids = ",".join(system_ids)
    tail_log_time_map = resource.databus.collector.bulk_system_collectors_status(
        namespace=namespace,
        system_ids=system_ids,
    )
    # 3. 获取资产上报信息
    snapshot_status_map = resource.databus.collector.bulk_system_snapshots_status(system_ids=system_ids)

    result = {}
    for system in systems:
        tail_log_item: TailLogStatusDict = tail_log_time_map.get(system["system_id"], {})
        snapshot_status_item: SnapshotStatusDict = snapshot_status_map.get(system["system_id"], {})
        tail_log_status: LogReportStatus = tail_log_item.get("status")
        has_permission_model = bool(system["action_count"] or system["resource_type_count"])
        snapshot_status: SnapshotReportStatus = snapshot_status_item.get("status")

        # 系统审计状态为未接入: 未接入
        if system["audit_status"] == SystemAuditStatusEnum.PENDING:
            status_detail = SystemStatusDetailEnum.PENDING
        # 没有权限模型 or 没有日志上报 or 没有配置资产上报: 待完善
        elif not has_permission_model:
            status_detail = SystemStatusDetailEnum.NO_PERMISSION_MODEL
        elif tail_log_status in (LogReportStatus.UNSET, None):
            status_detail = SystemStatusDetailEnum.NO_LOG_REPORT
        elif snapshot_status == SnapshotReportStatus.UNSET:
            status_detail = SystemStatusDetailEnum.NO_ASSET_REPORT
        # 资产上报异常 or 日志上报无数据: 数据异常
        elif tail_log_status == LogReportStatus.NODATA:
            status_detail = SystemStatusDetailEnum.LOG_NO_DATA
        elif snapshot_status == SnapshotReportStatus.ABNORMAL:
            status_detail = SystemStatusDetailEnum.ASSET_ABNORMAL
        # 系统接入 & 有权限模型 & 日志上报正常 & 资产上报： 数据正常
        else:
            status_detail = SystemStatusDetailEnum.NORMAL
        system_status = str(status_detail.system_status().value)
        system_status_msg = str(status_detail.label)
        system_stage = fetch_system_stage(
            system_status=system_status,
            has_permission_model=has_permission_model,
            has_collector=bool(tail_log_item.get("collector_count", 0)),
        )
        result[system["system_id"]] = SystemStatusDict(
            system_status=system_status,
            system_status_msg=system_status_msg,
            tail_log_item=tail_log_item,
            snapshot_status_item=snapshot_status_item,
            has_permission_model=has_permission_model,
            system_stage=system_stage,
        )
    return result


def fetch_system_stage(
    system_status: Union[SystemStatusEnum, str], has_permission_model: bool, has_collector: bool
) -> SystemStageEnum:
    """
    获取系统阶段信息
    """

    if system_status == SystemStatusEnum.PENDING.value:
        return SystemStageEnum.PENDING.value
    elif not has_permission_model:
        return SystemStageEnum.PERMISSION_MODEL.value
    elif not has_collector:
        return SystemStageEnum.COLLECTOR.value
    else:
        return SystemStageEnum.COMPLETED.value
