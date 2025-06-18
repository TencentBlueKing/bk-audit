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

import copy
import itertools
import json
import uuid
from collections import OrderedDict
from functools import wraps
from json import JSONDecodeError
from typing import Any, Iterator, List, Union

from bk_resource.base import Empty
from blueapps.utils.logger import logger

from core.constants import DEFAULT_JSON_EXPAND_SEPARATOR


def choices_to_dict(choice, val: str = "id", name: str = "name", *, exclude_vals: list = None):
    exclude_vals = exclude_vals or []
    return [
        {val: choice_value, name: str(choice_label)}
        for choice_value, choice_label in choice.choices
        if choice_value not in exclude_vals
    ]


def choices_to_select_list(choice_class) -> list:
    return [{"id": value, "name": str(label)} for value, label in choice_class.choices]


def choices_to_items(choice_class) -> dict:
    return {key: val for key, val in choice_class.choices}


def group_by(iter_list, key, sorted_key=None):
    if sorted_key:
        iter_list = sorted(iter_list, key=sorted_key)
    else:
        iter_list = sorted(iter_list, key=key)
    return {_id: list(group) for _id, group in itertools.groupby(iter_list, key)}


def distinct(instances) -> list:
    # 使用 Set 直接过滤
    try:
        return list({i for i in instances})
    # 无法 Set 则遍历过滤 (dict, list)
    except TypeError:
        _instances = list()
        for i in instances:
            if i not in _instances:
                _instances.append(i)
        return _instances


def replenish_params(data: dict, extra_data: dict) -> dict:
    replenish_keys = set(extra_data.keys()) - set(data.keys())
    for key in replenish_keys:
        data[key] = extra_data[key]
    return data


def expand_json(raw_json: dict, level: int) -> dict:
    """
    将Json展开，获取多层内容
    input: {"a": {"a-1": 1}}
    output: {"a": {"a-1": 1}, "a/a-1": 1}
    """
    data = dict()
    expanded_keys = set()
    current_level = 1
    while current_level < level:
        current_level += 1
        for key, val in raw_json.items():
            # 已经展开则跳过
            if key in expanded_keys:
                continue
            # 存入原始值
            data[key] = val
            expanded_keys.add(key)
            # 字典类型进行展开
            if isinstance(val, dict):
                for child_key, child_val in val.items():
                    data[f"{key}{DEFAULT_JSON_EXPAND_SEPARATOR}{child_key}"] = child_val
        # 处理结束后重新赋值原数据
        raw_json = copy.deepcopy(data)
    return data


def data_chunks(data: list, limit: int) -> Iterator[List]:
    """
    数据分块
    """

    for i in range(0, len(data), limit):
        # fmt: off
        yield data[i: i + limit]


def ignore_wrapper(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as err:  # pylint: disable=broad-except
            logger.exception("[WrapperError] Err => %s", err)

    return wrapper


def ordered_dict_to_json(data):
    if isinstance(data, list):
        _data = []
        for item in data:
            _data.append(ordered_dict_to_json(item))
        return _data
    if isinstance(data, (dict, OrderedDict)):
        _data = dict(data)
        for key, val in _data.items():
            _data[key] = ordered_dict_to_json(val)
        return _data
    return data


def trans_object_local(obj: Union[dict, List[dict]], fields: List[str]) -> Union[dict, List[dict]]:
    if isinstance(obj, list):
        return [trans_object_local(item, fields) for item in obj]
    for field in fields:
        obj[field] = str(obj[field])
    return obj


def modify_dict_by_path(data: dict, path: List[str], default_value: any, auto_create: bool = False) -> dict:
    # 如果内容为空直接返回
    if not data:
        return data
    # 首层直接替换
    if len(path) == 1:
        data[path[0]] = default_value
        return data
    # 第二层需要递归
    if auto_create:
        data[path[0]] = data.get(path[0]) or {}
    if data.get(path[0]) is None:
        return data
    # 递归更新下层内容
    data[path[0]] = modify_dict_by_path(data[path[0]], path[1:], default_value)
    return data


def drop_dict_item_by_path(data: dict, path: List[str], default_value: any) -> dict:
    # 如果内容为空直接返回
    if not data:
        return data
    # 首层直接移除
    if len(path) == 1:
        data.pop(path[0], None)
        return data
    # 第二层需要递归
    next_path = data.get(path[0])
    if not next_path:
        return data
    # 递归移除下层内容
    data[path[0]] = drop_dict_item_by_path(data[path[0]], path[1:], default_value)
    return data


def extract_nested_value(data: Any, keys: List[str]) -> Any:
    """
    根据给定的键列表从嵌套字典中提取值。
    :param data: 嵌套字典或字符串（尝试解析为JSON）
    :param keys: 键列表
    :return: 提取的值,未找到或异常返回 Empty()
    """

    current = data
    for key in keys:
        if not current:
            return Empty()
        # 处理字典类型
        if isinstance(current, dict):
            current = current.get(key, Empty())
        # 处理字符串类型（尝试解析为JSON）
        elif isinstance(current, str):
            try:
                current = json.loads(current)
                current = current.get(key, Empty()) if isinstance(current, dict) else Empty()
            except JSONDecodeError:
                return Empty()
        # 处理其他类型
        else:
            return Empty()
    return current


def unique_id():
    """生成32个字符的唯一ID ."""
    return uuid.uuid3(uuid.uuid1(), uuid.uuid4().hex).hex
