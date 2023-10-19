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

from services.web.databus.collector.etl.etl_config_handler.bk_log_json import JsonConfig


class BkBaseJsonConfig(JsonConfig):
    def build_config(self, next_config: dict) -> dict:
        next_assign = next_config["next"]["next"]
        return {
            "extract": {
                "type": "fun",
                "method": "from_json",
                "result": "json_data",
                "label": self.uniq_label_id(),
                "args": [],
                "next": {
                    "type": "branch",
                    "name": "",
                    "label": None,
                    "next": [
                        {
                            "type": "assign",
                            "subtype": "assign_json",
                            "label": self.uniq_label_id(),
                            "assign": [{"type": "text", "assign_to": "log", "key": "__all_keys__"}],
                            "next": None,
                        },
                        *self.build_custom_field_config(),
                        *next_assign,
                        {
                            "type": "assign",
                            "subtype": "assign_obj",
                            "label": self.uniq_label_id(),
                            "assign": self.assign_other_fields,
                            "next": None,
                        },
                    ],
                },
            },
            "conf": self.time_conf,
            "join": [],
        }
