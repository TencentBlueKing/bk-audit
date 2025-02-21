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
import re
from json import JSONDecodeError
from typing import List

from bk_resource import api
from bk_resource.exceptions import APIRequestError

from apps.exceptions import RegexpExpressionError
from core.constants import DEFAULT_JSON_EXPAND_SEPARATOR
from services.web.databus.collector.etl.base import EtlClean
from services.web.databus.collector.etl.etl_config_handler.bk_log_regexp import (
    RegexpConfig,
)
from services.web.databus.constants import EtlConfigEnum
from services.web.databus.models import CollectorConfig


class BkLogRegexpEtlClean(EtlClean):
    etl_config = EtlConfigEnum.BK_LOG_REGEXP.value

    def extract_keys(self, regexp: str) -> list:
        pattern = re.compile(r"\(\?P?\<([a-zA-Z0-9]+)\>")
        result = re.findall(pattern, regexp)
        return result

    def extract_value(self, data: dict) -> list:
        fields = []
        for key, val in data.items():
            try:
                json_data = json.loads(val)
                fields.append({"key": key, "val": json_data, "path": key})
                if not isinstance(json_data, dict):
                    continue
                for json_key, json_val in json_data.items():
                    fields.append(
                        {
                            "key": f"{key}{DEFAULT_JSON_EXPAND_SEPARATOR}{json_key}",
                            "val": json_val,
                            "path": f"{key}{DEFAULT_JSON_EXPAND_SEPARATOR}{json_key}",
                        }
                    )
            except JSONDecodeError:
                fields.append({"key": key, "val": val, "path": key})
        return fields

    def etl_preview(self, data: str, etl_params: dict):
        label_name = "label00001"
        regexp = etl_params["regexp"].replace("(?P<", "(?<")
        conf = {
            "type": "fun",
            "method": "regex_extract",
            "label": label_name,
            "args": [{"result": "data", "keys": self.extract_keys(regexp), "regexp": regexp}],
            "next": None,
        }
        try:
            resp = api.bk_base.clean_preview(msg=data, conf=json.dumps(conf), debug_by_step=True)
            return self.extract_value(resp.get("nodes", {}).get(label_name, {}))
        except APIRequestError:
            raise RegexpExpressionError()

    def get_bkbase_etl_config(self, collector_config: CollectorConfig, etl_params: dict, fields: List[dict]):
        etl_params["regexp_keys"] = self.extract_keys(etl_params["regexp"])
        etl_params["regexp"] = etl_params["regexp"].replace("(?P<", "(?<")
        return RegexpConfig(
            config_name=collector_config.collector_config_name,
            config_name_en=collector_config.collector_config_name_en,
            collector_config_id=collector_config.collector_config_id,
            data_id=collector_config.bk_data_id,
            fields=fields,
            system_id=collector_config.system_id,
            description=collector_config.description,
            etl_params=etl_params,
            join_data_rt=collector_config.join_data_rt,
        ).config
