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


def parse_nested_params(query_dict: dict) -> dict:
    """
    解析嵌套参数
    例如：
    {
        "k1": "value1",
        "constants[a]": "1",
        "constants[c][d]": "3"
    }
    解析为：
    {
        "k1": "value1",
        "constants": {
            "a": "1",
            "c": {
                "d": "3"
            }
        }
    }

    如果键名存在且不为字典，则会被放到一个名为 '__value__' 的键下
    例如:
    {
        "k1": "value1",
        "k1[a]": "1",
    }
    解析为：
    {
        "k1": {
            "__value__": "value1",
            "a": "1"
        }
    }
    """

    result = {}
    for key, value in query_dict.items():
        # 分解键名（兼容没有[]的普通参数）
        parts = key.replace(']', '').split('[')  # 例如 "constants[c][d]" -> ['constants', 'c', 'd']
        current = result
        for part in parts[:-1]:
            # 如果当前层级已存在但不是字典，则用字典包装原有值
            if part in current and not isinstance(current[part], dict):
                current[part] = {'__value__': current[part]}
            else:
                current.setdefault(part, {})
            current = current[part]
        last_key = parts[-1]
        # 如果当前最后键对应的值为字典且新值也是字典，则合并
        if isinstance(current.get(last_key), dict) and isinstance(value, dict):
            current[last_key].update(value)
        else:
            current[last_key] = value
    return result
