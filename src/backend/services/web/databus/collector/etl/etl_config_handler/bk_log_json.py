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

from services.web.databus.collector.etl.etl_config_handler.base import BkBaseConfig
from services.web.databus.constants import CustomTypeEnum


class JsonConfig(BkBaseConfig):
    @property
    def json_config(self):
        # 划分一二级字段
        (
            first_level_fields,
            first_level_json_fields,
            second_level_field_map,
            second_level_json_field_map,
        ) = self.check_field_level()
        # 生成Assign
        # 首层非JSON
        assigned_first_level_fields = [self.to_bkdata_assign(field) for field in first_level_fields]
        # 首层JSON
        assigned_first_level_json_fields = [self.to_bkdata_assign(field) for field in first_level_json_fields]
        # 兼容非JSON清洗
        if self.etl_params.get("use_json_string"):
            assigned_first_level_json_fields = [
                {
                    "type": "access",
                    "subtype": "access_obj",
                    "label": self.uniq_label_id(),
                    "key": field["field_name"],
                    "result": f"{field['field_name']}_extract_tmp",
                    "default_type": "null",
                    "default_value": "",
                    "next": {
                        "type": "fun",
                        "method": "from_json",
                        "result": f"{field['field_name']}_extract_json_tmp",
                        "label": self.uniq_label_id(),
                        "args": [],
                        "next": {
                            "type": "assign",
                            "subtype": "assign_json",
                            "label": self.uniq_label_id(),
                            "assign": [
                                {
                                    "type": "text",
                                    "assign_to": field["field_name"],
                                    "key": "__all_keys__",
                                }
                            ],
                            "next": None,
                        },
                    },
                }
                for field in first_level_json_fields
            ]
        # 二层非JSON
        assigned_second_level_fields = []
        for _, _parent_path in enumerate(second_level_field_map.keys(), 1):
            _config = {
                "type": "access",
                "subtype": "access_obj",
                "label": self.uniq_label_id(),
                "key": _parent_path,
                "result": _parent_path,
                "default_type": "null",
                "default_value": "",
                "next": {
                    "type": "branch",
                    "name": "",
                    "label": None,
                    "next": [
                        {
                            "type": "assign",
                            "subtype": "assign_obj",
                            "label": self.uniq_label_id(),
                            "assign": [self.to_bkdata_assign(field) for field in second_level_field_map[_parent_path]],
                            "next": None,
                        }
                    ],
                },
            }
            _config["next"]["next"].extend(self.add_next_assign_start_time(second_level_field_map[_parent_path]))
            assigned_second_level_fields.append(_config)
        # 二层JSON字段
        # 兼容OT日志，需要额外做一层反序列化
        assigned_second_level_json_fields = [
            {
                "type": "access",
                "subtype": "access_obj",
                "label": self.uniq_label_id(),
                "key": _parent_path,
                "result": f"{_parent_path}_json_tmp",
                "default_type": "null",
                "default_value": "",
                "next": {
                    "type": "branch",
                    "name": "",
                    "label": None,
                    "next": [
                        {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": self.uniq_label_id(),
                            "key": field["field_name"],
                            "result": f"{field['field_name']}_ot_tmp",
                            "default_type": "null",
                            "default_value": "",
                            "next": {
                                "type": "fun",
                                "method": "from_json",
                                "result": f"{field['field_name']}_ot_json_tmp",
                                "label": self.uniq_label_id(),
                                "args": [],
                                "next": {
                                    "type": "assign",
                                    "subtype": "assign_json",
                                    "label": self.uniq_label_id(),
                                    "assign": [
                                        {
                                            "type": "text",
                                            "assign_to": field["field_name"],
                                            "key": "__all_keys__",
                                        }
                                    ],
                                    "next": None,
                                },
                            },
                        }
                        for field in second_level_json_field_map[_parent_path]
                    ],
                }
                if self.collector.custom_type == CustomTypeEnum.OTLP_LOG.value
                else {
                    "type": "assign",
                    "subtype": "assign_json",
                    "label": self.uniq_label_id(),
                    "assign": [self.to_bkdata_assign(field) for field in second_level_json_field_map[_parent_path]],
                    "next": None,
                },
            }
            for index, _parent_path in enumerate(second_level_json_field_map.keys(), 1)
        ]
        # 配置一级非JSON字段
        next_assign_obj = []
        if assigned_first_level_fields:
            next_assign_obj.extend(
                [
                    {
                        "type": "assign",
                        "subtype": "assign_obj",
                        "label": self.uniq_label_id(),
                        "assign": assigned_first_level_fields,
                        "next": None,
                    },
                ]
            )
            # 配置时间字段
            next_assign_obj.extend(self.add_next_assign_start_time(first_level_fields))
        # 配置一级JSON字段
        if assigned_first_level_json_fields:
            if self.etl_params.get("use_json_string"):
                next_assign_obj.extend(assigned_first_level_json_fields)
            else:
                next_assign_obj.extend(
                    [
                        {
                            "type": "assign",
                            "subtype": "assign_json",
                            "label": self.uniq_label_id(),
                            "assign": assigned_first_level_json_fields,
                            "next": None,
                        }
                    ]
                )
        # 配置二级非JSON字段
        if assigned_second_level_fields:
            next_assign_obj.extend(assigned_second_level_fields)
        # 配置二级JSON字段
        if assigned_second_level_json_fields:
            next_assign_obj.extend(assigned_second_level_json_fields)
        # Config
        config = self.trans_config(
            {
                "type": "fun",
                "method": "from_json",
                "result": "log_json",
                "label": self.uniq_label_id(),
                "args": [],
                "next": {
                    "type": "branch",
                    "name": "",
                    "label": None,
                    "next": next_assign_obj,
                },
            }
        )
        return config
