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

import json
from typing import List

from apps.exceptions import JsonLoadsError
from core.constants import DEFAULT_JSON_EXPAND_LEVEL
from core.utils.data import expand_json
from services.web.databus.collector.etl.base import EtlClean
from services.web.databus.collector.etl.etl_config_handler.bk_log_json import JsonConfig
from services.web.databus.constants import EtlConfigEnum
from services.web.databus.models import CollectorConfig


class BkLogJsonEtlClean(EtlClean):
    etl_config = EtlConfigEnum.BK_LOG_JSON.value

    def etl_preview(self, data: str, etl_params: dict) -> list:
        try:
            data = json.loads(data)
        except Exception:
            raise JsonLoadsError()
        expanded_data = expand_json(data, DEFAULT_JSON_EXPAND_LEVEL)
        return [{"key": key, "val": val, "path": key} for key, val in expanded_data.items()]

    def get_bkbase_etl_config(self, collector_config: CollectorConfig, etl_params: dict, fields: List[dict]):
        etl_handler = JsonConfig(
            config_name=collector_config.collector_config_name,
            config_name_en=collector_config.collector_config_name_en,
            collector_config_id=collector_config.collector_config_id,
            data_id=collector_config.bk_data_id,
            fields=fields,
            system_id=collector_config.system_id,
            description=collector_config.description,
            etl_params=etl_params,
            join_data_rt=collector_config.join_data_rt,
        )
        return etl_handler.config
