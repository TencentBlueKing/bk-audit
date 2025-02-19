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

from collections import defaultdict

from blueapps.utils.base import ignored
from blueapps.utils.unique import uniqid
from django.conf import settings
from django.utils.translation import gettext

from apps.exceptions import MetaConfigNotExistException, TimeFieldMissing
from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.fields import (
    BK_DATA_ID,
    BKAUDIT_BUILD_IN_FIELDS,
    BKDATA_ES_TYPE_MAP,
    EXT_FIELD_CONFIG,
    FIELD_TYPE_OBJECT,
    FIELD_TYPE_STRING,
    FIELD_TYPE_TEXT,
    SNAPSHOT_ACTION_INFO,
    SNAPSHOT_RESOURCE_TYPE_INFO,
    SNAPSHOT_USER_INFO,
    START_TIME,
)
from core.constants import DEFAULT_JSON_EXPAND_SEPARATOR
from core.models import get_request_username
from services.web.databus.collector.snapshot.join.base import JoinConfig
from services.web.databus.collector_plugin.handlers import PluginEtlHandler
from services.web.databus.constants import (
    ACTION_DATA_RT_KEY,
    DEFAULT_TIME_FORMAT,
    DEFAULT_TIME_LEN,
    DEFAULT_TIME_ZONE,
    RESOURCE_TYPE_DATA_RT_KEY,
    USER_INFO_DATA_RT_KEY,
    SourcePlatformChoices,
)
from services.web.databus.models import CollectorConfig


class BkBaseConfig:
    def __init__(
        self,
        config_name: str,
        config_name_en: str,
        collector_config_id: int,
        data_id: int,
        fields: list,
        system_id: str,
        description: str = None,
        etl_params: dict = None,
        join_data_rt: str = None,
    ):
        self.bk_username = get_request_username()
        self.config_name = config_name
        self.config_name_en = config_name_en
        self.collector_config_id = str(collector_config_id)
        self.description = description
        self.data_id = data_id
        self.fields = fields
        self.field_map = self._init_field_map(fields)
        self.etl_params = etl_params
        self.system_id = system_id
        self.label_ids = set()
        self.join_data_rt = join_data_rt
        self.collector = CollectorConfig.objects.get(collector_config_id=self.collector_config_id)

    def _init_field_map(self, fields: list) -> dict:
        return {field["field_name"]: field for field in fields}

    @property
    def config(self) -> dict:
        return {
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "bk_username": self.bk_username,
            "clean_config_name": self.config_name,
            "description": self.description or self.config_name,
            "fields": PluginEtlHandler.get_fields(),
            "json_config": self.json_config,
            "raw_data_id": self.data_id,
            "result_table_name": f"bklog_{self.config_name_en.lower()}",
            "result_table_name_alias": self.config_name_en.lower(),
            "result_table_id": "{}_{}".format(
                settings.DEFAULT_BK_BIZ_ID, PluginEtlHandler(self.collector.collector_plugin_id).get_table_id()
            ),
            "processing_id": CollectorConfig.make_table_id(
                settings.DEFAULT_BK_BIZ_ID, self.collector.collector_config_name_en
            ).replace(".", "_"),
        }

    def parse_field_name(self, parent_field_name: str, field_name: str) -> str:
        return field_name.replace(f"{parent_field_name}.", "", 1)

    def to_bkdata_assign(self, field: dict, is_index: bool = False, assign_to: str = None) -> dict:
        # 支持使用 option.path 指定
        key = field.get("option", {}).get("path") or field["field_name"]
        # 映射 key => assign_to
        assign_obj = {
            "key": key,
            "assign_to": assign_to or field["field_name"],
            "type": BKDATA_ES_TYPE_MAP.get(field["field_type"], FIELD_TYPE_STRING),
        }
        # 兼容分隔符的index
        if not is_index:
            return assign_obj
        assign_obj["index"] = assign_obj.pop("key")
        return assign_obj

    @property
    def time_conf(self) -> dict:
        time_field = None
        for field in self.fields:
            if field["is_time"]:
                time_field = field
                break
        if time_field is None:
            raise TimeFieldMissing()
        return {
            "output_field_name": "timestamp",
            "time_format": time_field["option"].get("time_format", DEFAULT_TIME_FORMAT),
            "timezone": time_field["option"].get("time_zone", DEFAULT_TIME_ZONE),
            "encoding": "UTF-8",
            "timestamp_len": time_field["option"].get("time_len", DEFAULT_TIME_LEN),
            "time_field_name": time_field.get("field_name"),
        }

    @property
    def build_in_fields(self) -> list:
        fields = PluginEtlHandler.get_build_in_fields()
        return fields

    @property
    def assign_build_in_fields(self):
        return [self.to_bkdata_assign(field) for field in self.build_in_fields if field["field_name"] != "time"]

    @property
    def assign_other_fields(self):
        all_fields = PluginEtlHandler.get_fields()
        current_fields = [f["field_name"] for f in self.result_table_fields]
        assign_fields = [
            field for field in all_fields if field["field_name"] not in current_fields and field["field_name"] != "time"
        ]
        return [self.to_bkdata_assign(field) for field in assign_fields]

    @property
    def result_table_fields(self):
        fields = [
            {
                "field_name": "log",
                "field_type": "text",
                "field_alias": gettext("原始日志"),
                "is_dimension": False,
                "field_index": 1,
            },
        ]
        if self.collector.source_platform == SourcePlatformChoices.BKLOG.value:
            fields.extend(
                [
                    {
                        "field_name": "iterationIndex",
                        "field_type": "long",
                        "field_alias": gettext("迭代ID"),
                        "is_dimension": False,
                        "field_index": 2,
                    },
                    {
                        "field_name": EXT_FIELD_CONFIG.field_name,
                        "field_type": BKDATA_ES_TYPE_MAP.get(EXT_FIELD_CONFIG.field_type, FIELD_TYPE_TEXT),
                        "field_alias": str(EXT_FIELD_CONFIG.description),
                        "is_dimension": EXT_FIELD_CONFIG.is_dimension,
                        "field_index": 3,
                    },
                ]
            )
            fields.extend(self.build_in_fields)
        fields.extend(
            [
                {
                    "field_name": field.field_name,
                    "field_type": BKDATA_ES_TYPE_MAP.get(field.field_type, FIELD_TYPE_STRING),
                    "field_alias": str(field.description),
                    "is_dimension": field.is_dimension,
                    "field_index": index,
                }
                for index, field in enumerate(BKAUDIT_BUILD_IN_FIELDS, 14)
            ]
        )
        fields.extend(
            [
                {
                    "field_name": field["field_name"],
                    "field_type": BKDATA_ES_TYPE_MAP.get(field["field_type"], FIELD_TYPE_STRING),
                    "field_alias": field.get("description") or field.get("alias_name") or field.get("field_name"),
                    "is_dimension": field["is_dimension"],
                    "field_index": index,
                }
                for index, field in enumerate(self.fields, 20)
            ]
        )
        with ignored(MetaConfigNotExistException):
            if GlobalMetaConfig.get(RESOURCE_TYPE_DATA_RT_KEY):
                fields.append(
                    {
                        "field_name": SNAPSHOT_RESOURCE_TYPE_INFO.field_name,
                        "field_type": BKDATA_ES_TYPE_MAP.get(
                            SNAPSHOT_RESOURCE_TYPE_INFO.field_type, SNAPSHOT_RESOURCE_TYPE_INFO.field_type
                        ),
                        "field_alias": SNAPSHOT_RESOURCE_TYPE_INFO.alias_name,
                        "is_dimension": SNAPSHOT_RESOURCE_TYPE_INFO.is_dimension,
                        "field_index": 12,
                        "is_json": True,
                    }
                )
        with ignored(MetaConfigNotExistException):
            if GlobalMetaConfig.get(ACTION_DATA_RT_KEY):
                fields.append(
                    {
                        "field_name": SNAPSHOT_ACTION_INFO.field_name,
                        "field_type": BKDATA_ES_TYPE_MAP.get(
                            SNAPSHOT_ACTION_INFO.field_type, SNAPSHOT_ACTION_INFO.field_type
                        ),
                        "field_alias": SNAPSHOT_ACTION_INFO.alias_name,
                        "is_dimension": SNAPSHOT_ACTION_INFO.is_dimension,
                        "field_index": 13,
                        "is_json": True,
                    }
                )
        with ignored(MetaConfigNotExistException):
            if GlobalMetaConfig.get(USER_INFO_DATA_RT_KEY):
                fields.append(
                    {
                        "field_name": SNAPSHOT_USER_INFO.field_name,
                        "field_type": BKDATA_ES_TYPE_MAP.get(
                            SNAPSHOT_USER_INFO.field_type, SNAPSHOT_ACTION_INFO.field_type
                        ),
                        "field_alias": SNAPSHOT_USER_INFO.alias_name,
                        "is_dimension": SNAPSHOT_USER_INFO.is_dimension,
                        "field_index": 14,
                        "is_json": True,
                    }
                )
        if self.join_data_rt:
            fields.extend(JoinConfig.fields())
        return fields

    @property
    def json_config(self):
        raise NotImplementedError

    def check_start_time_field(self, fields: list) -> dict:
        for field in fields:
            if field["field_name"] == START_TIME.field_name:
                return field
        return {}

    def add_next_assign_start_time(self, fields: list, is_index: bool = False) -> list:
        start_time_field = self.check_start_time_field(fields)
        if start_time_field:
            return [
                {
                    "type": "assign",
                    "subtype": "assign_pos" if is_index else "assign_obj",
                    "label": self.uniq_label_id(),
                    "assign": [self.to_bkdata_assign(start_time_field, is_index=is_index, assign_to="time")],
                    "next": None,
                },
            ]
        return []

    def check_field_level(self) -> (list, list, dict, dict):
        # 划分一二级字段
        first_level_fields = []
        first_level_json_fields = []
        second_level_fields = []
        second_level_json_fields = []
        for field in self.fields:
            if field["option"]["path"].find(DEFAULT_JSON_EXPAND_SEPARATOR) == -1:
                if field["field_type"] == FIELD_TYPE_OBJECT:
                    first_level_json_fields.append(field)
                else:
                    first_level_fields.append(field)
            else:
                if field["field_type"] == FIELD_TYPE_OBJECT:
                    second_level_json_fields.append(field)
                else:
                    second_level_fields.append(field)
        # 二级字段需要聚合到同一级后进行映射
        second_level_field_map = defaultdict(list)
        second_level_json_field_map = defaultdict(list)
        for field in second_level_fields:
            parent_path, field["option"]["path"] = field["option"]["path"].split(DEFAULT_JSON_EXPAND_SEPARATOR, 1)
            second_level_field_map[parent_path].append(field)
        for field in second_level_json_fields:
            parent_path, field["option"]["path"] = field["option"]["path"].split(DEFAULT_JSON_EXPAND_SEPARATOR, 1)
            second_level_json_field_map[parent_path].append(field)
        return first_level_fields, first_level_json_fields, second_level_field_map, second_level_json_field_map

    def uniq_label_id(self) -> str:
        label_id = f"label{uniqid()[:5]}"
        if label_id not in self.label_ids:
            self.label_ids.add(label_id)
            return label_id
        return self.uniq_label_id()

    def build_custom_field_config(self) -> list:
        return [
            {
                "type": "access",
                "subtype": "access_obj",
                "label": self.uniq_label_id(),
                "key": "__system_id",
                "result": "__system_id",
                "default_type": "string",
                "default_value": self.system_id,
                "next": {
                    "type": "assign",
                    "subtype": "assign_value",
                    "label": self.uniq_label_id(),
                    "assign": {"type": "string", "assign_to": "system_id"},
                    "next": None,
                },
            },
            {
                "type": "access",
                "subtype": "access_obj",
                "label": self.uniq_label_id(),
                "key": "__collector_config_id",
                "result": "__collector_config_id",
                "default_type": "int",
                "default_value": self.collector_config_id,
                "next": {
                    "type": "assign",
                    "subtype": "assign_value",
                    "label": self.uniq_label_id(),
                    "assign": {"type": "int", "assign_to": "collector_config_id"},
                    "next": None,
                },
            },
            {
                "type": "access",
                "subtype": "access_obj",
                "label": self.uniq_label_id(),
                "key": "__bk_data_id",
                "result": "__bk_data_id",
                "default_type": BK_DATA_ID.field_type,
                "default_value": self.data_id,
                "next": {
                    "type": "assign",
                    "subtype": "assign_value",
                    "label": self.uniq_label_id(),
                    "assign": {"type": BK_DATA_ID.field_type, "assign_to": BK_DATA_ID.field_name},
                    "next": None,
                },
            },
        ]

    def build_config(self, next_config: dict) -> dict:
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
                        *self.build_custom_field_config(),
                        {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": self.uniq_label_id(),
                            "key": "items",
                            "result": "item_data",
                            "default_type": "null",
                            "default_value": "",
                            "next": {
                                "type": "fun",
                                "label": self.uniq_label_id(),
                                "result": "iter_item",
                                "args": [],
                                "method": "iterate",
                                "next": {
                                    "type": "branch",
                                    "name": "",
                                    "label": None,
                                    "next": [
                                        {
                                            "type": "assign",
                                            "subtype": "assign_obj",
                                            "label": self.uniq_label_id(),
                                            "assign": [
                                                {"type": "text", "assign_to": "log", "key": "data"},
                                                {
                                                    "type": "long",
                                                    "assign_to": "iterationIndex",
                                                    "key": "iterationindex",
                                                },
                                            ],
                                            "next": None,
                                        },
                                        {
                                            "type": "access",
                                            "subtype": "access_obj",
                                            "label": self.uniq_label_id(),
                                            "key": "data",
                                            "result": "log_data",
                                            "default_type": "null",
                                            "default_value": "",
                                            "next": next_config,
                                        },
                                    ],
                                },
                            },
                        },
                        {
                            "type": "assign",
                            "subtype": "assign_obj",
                            "label": self.uniq_label_id(),
                            "assign": self.assign_build_in_fields,
                            "next": None,
                        },
                        {
                            "type": "assign",
                            "subtype": "assign_json",
                            "label": self.uniq_label_id(),
                            "assign": [
                                {
                                    "type": BKDATA_ES_TYPE_MAP.get(EXT_FIELD_CONFIG.field_type),
                                    "assign_to": EXT_FIELD_CONFIG.field_name,
                                    "key": EXT_FIELD_CONFIG.option["path"],
                                }
                            ],
                            "next": None,
                        },
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

    def trans_config(self, next_config: dict) -> dict:
        config = self.build_config(next_config)
        # 增加资源类型关联
        resource_type_rt = None
        with ignored(MetaConfigNotExistException):
            resource_type_rt = GlobalMetaConfig.get(RESOURCE_TYPE_DATA_RT_KEY)
            config["join"].append(
                {
                    "result_table_id": resource_type_rt,
                    "join_on": [
                        {"this_field": "system_id", "target_field": "system_id"},
                        {"this_field": "resource_type_id", "target_field": "id"},
                    ],
                    "select": [
                        {"field_name": "data", "type": FIELD_TYPE_TEXT, "as": SNAPSHOT_RESOURCE_TYPE_INFO.field_name}
                    ],
                }
            )
        # 增加操作关联
        action_rt = None
        with ignored(MetaConfigNotExistException):
            action_rt = GlobalMetaConfig.get(ACTION_DATA_RT_KEY)
            config["join"].append(
                {
                    "result_table_id": action_rt,
                    "join_on": [
                        {"this_field": "system_id", "target_field": "system_id"},
                        {"this_field": "action_id", "target_field": "id"},
                    ],
                    "select": [{"field_name": "data", "type": FIELD_TYPE_TEXT, "as": SNAPSHOT_ACTION_INFO.field_name}],
                }
            )
        # 增加用户数据关联
        user_info_rt = None
        with ignored(MetaConfigNotExistException):
            user_info_rt = GlobalMetaConfig.get(USER_INFO_DATA_RT_KEY)
            config["join"].append(
                {
                    "result_table_id": user_info_rt,
                    "join_on": [
                        {"this_field": "username", "target_field": "id"},
                    ],
                    "select": [{"field_name": "data", "type": FIELD_TYPE_TEXT, "as": SNAPSHOT_USER_INFO.field_name}],
                }
            )
        # 数据关联
        if self.join_data_rt:
            config["join"].append(JoinConfig(self.join_data_rt).config)
        if not resource_type_rt and not action_rt and not self.join_data_rt:
            config.pop("join")
        return config
