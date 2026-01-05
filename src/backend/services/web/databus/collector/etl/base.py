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

from bk_resource import api
from bk_resource.base import Empty
from django.conf import settings
from django.utils.module_loading import import_string
from django.utils.translation import gettext

from apps.meta.utils.fields import PYTHON_FIELD_TYPE_MAP
from core.models import get_request_username
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
    ) -> None:
        # 校验字段类型是否匹配
        self.check_field_type(fields)

        instance_fields = copy.deepcopy(fields)
        instance: CollectorConfig = CollectorConfig.objects.get(collector_config_id=collector_config_id)

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

        # 获取清洗入库
        bkbase_params = self.get_bkbase_etl_config(instance, etl_params, fields)

        # 结构转换
        bkbase_params["json_config"] = json.dumps(bkbase_params["json_config"])

        # 创建清洗
        if not instance.bkbase_table_id:
            result = api.bk_base.databus_cleans_post(bkbase_params)
            self.start_bkbase_clean(
                bkbase_params["result_table_id"],
                bkbase_params["processing_id"],
            )
            instance.processing_id = result["processing_id"]
            instance.bkbase_table_id = result["result_table_id"]
            instance.save()

        # 更新清洗
        else:
            bkbase_params.update({"processing_id": bkbase_params["processing_id"]})
            api.bk_base.databus_cleans_put(bkbase_params, request_cookies=False)
            self.restart_bkbase_clean(bkbase_params["result_table_id"], bkbase_params["processing_id"])

        instance.fields = instance_fields
        instance.etl_config = self.etl_config
        instance.etl_params = etl_params
        instance.save()

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
