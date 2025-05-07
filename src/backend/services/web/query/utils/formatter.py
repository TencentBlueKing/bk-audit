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
from json import JSONDecodeError
from typing import List, Union

from apps.bk_crypto.crypto import asymmetric_cipher
from apps.meta.constants import (
    SENSITIVE_REPLACE_VALUE,
    SensitiveResourceTypeEnum,
    SensitiveUserData,
)
from apps.meta.models import DataMap, SensitiveObject
from apps.meta.utils.fields import (
    EXTEND_DATA,
    INSTANCE_DATA,
    INSTANCE_ORIGIN_DATA,
    SNAPSHOT_ACTION_INFO,
    SNAPSHOT_INSTANCE_DATA,
    SNAPSHOT_RESOURCE_TYPE_INFO,
    SNAPSHOT_USER_INFO,
)
from core.utils.data import (
    choices_to_items,
    drop_dict_item_by_path,
    modify_dict_by_path,
)
from core.utils.time import mstimestamp_to_date_string
from services.web.query.constants import (
    AccessTypeChoices,
    ResultCodeChoices,
    UserIdentifyTypeChoices,
)
from services.web.risk.constants import EventMappingFields

JSON_FORMAT = [
    INSTANCE_DATA.field_name,
    INSTANCE_ORIGIN_DATA.field_name,
    EXTEND_DATA.field_name,
    SNAPSHOT_USER_INFO.field_name,
    SNAPSHOT_RESOURCE_TYPE_INFO.field_name,
    SNAPSHOT_ACTION_INFO.field_name,
    SNAPSHOT_INSTANCE_DATA.field_name,
    EventMappingFields.EVENT_DATA.field_name,
]


class HitsFormatter:
    """格式化数据输出"""

    def __init__(self, hit: dict, sensitive_objs: List[SensitiveObject]):
        self.hit = hit
        self.sensitive_objs = sensitive_objs
        self._format_hit()
        self._format_sensitive_data()

    @property
    def value(self):
        return self.hit

    def _format_hit(self):
        for key, val in self.hit.items():
            self.hit[key] = self._format(key, val)

    def _format(self, key: str, val: any) -> any:
        if key in JSON_FORMAT:
            val = self._loads_json(val)
        formatter = getattr(self, f"_format_{key}", None)
        if callable(formatter):
            return formatter(val)
        return val

    def _format_start_time(self, value: int) -> str:
        if not value:
            return ""
        return mstimestamp_to_date_string(value)

    def _format_end_time(self, value: int) -> str:
        if not value:
            return ""
        return mstimestamp_to_date_string(value)

    def _format_access_type(self, value: str) -> str:
        return str(choices_to_items(AccessTypeChoices).get(str(value), value))

    def _format_result_code(self, value: str) -> str:
        return "{}({})".format(
            ResultCodeChoices.SUCCESS.label
            if str(value) == ResultCodeChoices.SUCCESS.value
            else ResultCodeChoices.FAILED.label,
            value,
        )

    def _format_result_content(self, val: str) -> str:
        if isinstance(val, str):
            val = val.replace("\x00", "")
        return val

    def _format_user_identify_type(self, value) -> str:
        return str(choices_to_items(UserIdentifyTypeChoices).get(str(value), value))

    def _loads_json(self, value: Union[str, dict]) -> Union[str, dict]:
        if not value:
            return {}
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value) or dict()
        except (TypeError, JSONDecodeError):
            return value

    def _format_snapshot_user_info(self, value: dict) -> dict:
        data = DataMap.trans_data(value, list(value.keys()), build_data_fields=lambda x: f"snapshot_user_info__{x}")
        # 加密用户数据
        for key, val in data.items():
            data[key] = asymmetric_cipher.encrypt(val)
        return data

    def _format_sensitive_data(self):
        # 默认拥有所有权限
        _all_permission = True
        for so in self.sensitive_objs:
            # IAM 权限
            has_permission = getattr(so, "_has_permission", False)
            # 该条日志是否匹配
            match_condition = self._check_sensitive_condition(so)
            # 有权限或不匹配则跳过
            if has_permission or not match_condition:
                continue
            # 没有权限 且 匹配 且 不是移除的内容
            if not has_permission and match_condition and not so.is_private:
                _all_permission = False
            # 逐个字段进行替换或移除
            for field in so.fields:
                field_path = field["field_name"].split(".")
                default_value = field.get("default_value", SENSITIVE_REPLACE_VALUE)
                args = (self.hit, field_path, default_value)
                self.hit = drop_dict_item_by_path(*args) if so.is_private else modify_dict_by_path(*args)
        # 没有所有权限时，需要隐藏原始日志
        if not _all_permission:
            self.hit["log"] = SENSITIVE_REPLACE_VALUE

    def _check_sensitive_condition(self, sensitive_obj: SensitiveObject) -> bool:
        if sensitive_obj.resource_type == SensitiveResourceTypeEnum.RESOURCE.value:
            # 系统ID相同且资源类型相同 或 用户管理下的用户信息
            return (
                self.hit.get("system_id") == sensitive_obj.system_id
                and self.hit.get("resource_type_id", "") == sensitive_obj.resource_id
                or sensitive_obj.system_id == SensitiveUserData.SYSTEM_ID
                and sensitive_obj.resource_id == SensitiveUserData.RESOURCE_ID
            )
        elif sensitive_obj.resource_type == SensitiveResourceTypeEnum.ACTION.value:
            # 系统ID相同且操作相同
            return (
                self.hit.get("system_id") == sensitive_obj.system_id
                and self.hit.get("action_id", "") == sensitive_obj.resource_id
            )
