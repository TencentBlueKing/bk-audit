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

import abc
import copy
import json
from typing import List

from bk_resource.base import Empty
from django.conf import settings
from django.utils.module_loading import import_string
from django.utils.translation import gettext

from apps.exceptions import SnapshotPreparingException
from apps.meta.utils.fields import PYTHON_FIELD_TYPE_MAP
from core.models import get_request_username
from services.web.bkbase import clean as bkbase_clean
from services.web.bkbase.common import (
    get_bkbase_context,
    get_bkbase_version,
    resource_lock,
)
from services.web.bkbase.constants import BKBaseVersion, TaskState
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.constants import (
    JOIN_DATA_RT_FORMAT,
    EtlConfigEnum,
    JoinDataType,
)
from services.web.databus.models import CollectorConfig, Snapshot
from services.web.databus.utils import restart_bkbase_clean, start_bkbase_clean


class EtlClean(metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    def etl_config(self):
        ...

    @classmethod
    def get_instance(cls, etl_config: str):
        mapping = {
            EtlConfigEnum.BK_LOG_JSON.value: "BkLogJsonEtlClean",
            EtlConfigEnum.BK_LOG_DELIMITER.value: "BkLogDelimiterEtlClean",
            EtlConfigEnum.BK_LOG_REGEXP.value: "BkLogRegexpEtlClean",
            EtlConfigEnum.BK_BASE_JSON.value: "BkBaseJsonEtlClean",
        }
        try:
            etl_clean = import_string("databus.collector.etl.{}.{}".format(etl_config, mapping.get(etl_config)))
            return etl_clean()
        except ImportError as error:
            raise NotImplementedError(f"{etl_config} not implement, error: {error}")

    def etl_preview(self, *args, **kwargs):
        raise NotImplementedError

    def get_bkbase_etl_config(self, collector_config: CollectorConfig, etl_params: dict, fields: List[dict]):
        raise NotImplementedError

    def update_or_create(
        self,
        collector_config_id: int,
        etl_params: dict,
        fields: List[dict],
        namespace: str,
        *,
        retry_rejected_create: bool = False,
    ) -> None:
        # 校验字段类型是否匹配
        self.check_field_type(fields)
        instance: CollectorConfig = CollectorConfig.objects.get(collector_config_id=collector_config_id)

        if get_bkbase_version() == BKBaseVersion.V4:
            context = get_bkbase_context()
            ref = bkbase_clean.owner_clean_ref(context, instance)
            with resource_lock(context, ref):
                instance = CollectorConfig.objects.get(pk=instance.pk)
                if bkbase_clean.owner_clean_ref(context, instance) != ref:
                    raise BKBaseResourceMappingError(message="Collector Clean binding changed under lock")
                self._check_restore_write(instance)
                self._save_clean(
                    instance, etl_params, fields, locked_ref=ref, retry_rejected_create=retry_rejected_create
                )
            return

        # 新建的采集需要自动关联
        if not instance.join_data_rt:
            snapshots = Snapshot.objects.filter(
                system_id=instance.system_id, join_data_type=JoinDataType.BASIC.value
            ).exclude(bkbase_table_id=None)
            if snapshots.count():
                snapshot = snapshots.first()
                rt_name = JOIN_DATA_RT_FORMAT.format(
                    system_id=snapshot.system_id, resource_type_id=snapshot.resource_type_id
                ).replace("-", "_")
                instance.join_data_rt = f"{settings.DEFAULT_BK_BIZ_ID}_{rt_name}"
        self._save_clean(instance, etl_params, fields)

    @staticmethod
    def _check_restore_write(instance):
        """Clean PUT 与生效观察之间，保留快照已认领的关联配置。"""
        snapshots = Snapshot.objects.filter(system_id=instance.system_id, join_data_type=JoinDataType.BASIC)
        for binding in snapshots.values_list("bkbase_v4_resources", flat=True):
            if not isinstance(binding, dict):
                continue
            operation = binding.get("source_replay") or {}
            if not isinstance(operation, dict) or operation.get("mode") != "restore":
                continue
            write = (operation.get("writes") or {}).get(f"collector:{instance.pk}")
            if write and (
                operation.get("active")
                or not write.get("linked")
                and (operation.get("outcome_unknown") or write.get("observed") == TaskState.PENDING)
            ):
                raise SnapshotPreparingException()

    def _save_clean(self, instance, etl_params, fields, *, locked_ref=None, retry_rejected_create=False):
        """生成规则并保存本次编辑的本地配置。"""
        instance_fields = copy.deepcopy(fields)

        # 获取清洗入库
        bkbase_params = self.get_bkbase_etl_config(instance, etl_params, fields)

        # 结构转换
        bkbase_params["json_config"] = json.dumps(bkbase_params["json_config"])

        if locked_ref is None:
            bkbase_clean.configure_clean(instance, bkbase_params, rt_owner=False)
        else:
            retry = bkbase_clean.rejected_collector_create_retry(instance) if retry_rejected_create else {}
            bkbase_clean.configure_clean(instance, bkbase_params, rt_owner=False, _locked_clean_ref=locked_ref, **retry)

        instance.fields = instance_fields
        instance.etl_config = self.etl_config
        instance.etl_params = etl_params
        if locked_ref is None:
            instance.save()
        else:
            instance.save(update_fields=["fields", "etl_config", "etl_params"])

    @classmethod
    def check_field_type(cls, fields: List[dict]):
        """检查字段类型"""

        for field in fields:
            py_field_type = PYTHON_FIELD_TYPE_MAP.get(field.get("field_type"))
            if not py_field_type:
                continue
            field_value = field.get("option", {}).get("val", Empty())
            if isinstance(field_value, Empty) or isinstance(field_value, py_field_type) or not field_value:
                continue
            raise ValueError(
                gettext("%s 应为 %s 类型，当前值为 %s")
                % (
                    field.get("description", field["field_name"]),
                    field.get("field_type"),
                    type(field.get("option", {}).get("val")).__name__,
                )
            )

    @staticmethod
    def start_bkbase_clean(bkbase_result_table_id: str, processing_id: str) -> None:
        """
        启动清洗任务
        """

        start_bkbase_clean(bkbase_result_table_id, processing_id, get_request_username())

    @staticmethod
    def restart_bkbase_clean(bkbase_result_table_id: str, processing_id: str) -> None:
        """
        重启清洗任务
        """

        restart_bkbase_clean(bkbase_result_table_id, processing_id, get_request_username())
