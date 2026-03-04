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

# Mock 数据
MOCK_TOOL_CONFIG = {
    "sql": "SELECT * FROM table WHERE time = ${time_range}",
    "referenced_tables": [{"table_name": "table"}],
    "input_variable": [],
    "output_fields": [],
    "prefer_storage": "doris",
}

MOCK_EXECUTE_PARAMS = {
    "tool_variables": [{"raw_name": "time_range", "value": "2023-01-01,2023-12-31"}],
    "page": 1,
    "page_size": 100,
}

MOCK_API_RESPONSE = [
    {"list": [{"field1": "value1"}, {"field2": "value2"}]},  # 数据查询结果
    {"list": [{"count": 2}]},  # 计数查询结果
]

MOCK_FETCH_TOOL_PERMISSION_TAGS_EMPTY = {
    "use_tool_permission_tags": set(),
    "manage_tool_permission_tags": set(),
}


def mock_wrapper_permission_field(result_list, *args, **kwargs):
    """
    Mock wrapper_permission_field 函数，直接返回结果列表，
    并为每个结果添加默认的权限字段
    """
    for item in result_list:
        item["permission"] = {
            "use_tool": True,
            "manage_tool": True,
        }
    return result_list
