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
import secrets
import string
import uuid
from collections import OrderedDict
from functools import wraps
from json import JSONDecodeError
from typing import Any, Callable, Iterator, List, Union

from bk_resource.base import Empty
from blueapps.utils.logger import logger
from django.db.models import QuerySet
from django.db.models.enums import ChoicesMeta

from core.choices import Unset
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


def value_to_label(choice: ChoicesMeta, value, default=Unset):
    """
    将值转换为标签
    :param choice: 选择类
    :param value: 值
    :param default: 默认值, 默认为 value
    """

    if default is Unset:
        default = value
    return str(dict(choice.choices).get(value, default))


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


def generate_random_string(length=32, alphabet=None):
    """
    生成一个指定长度的随机字符串。

    :param length: 随机字符串的长度，默认为 32
    :param alphabet: 字符集，默认为字母和数字的组合，如果需要自定义字符集可以传入
    :return: 生成的随机字符串
    """

    # 默认字符集：字母（小写和大写）和数字
    if alphabet is None:
        alphabet = string.ascii_letters + string.digits

    return ''.join(secrets.choice(alphabet) for _ in range(length))


def get_value_by_request(request, key: str):
    return request.query_params.get(key, request.data.get(key))


def compare_dict_specific_keys(d1: dict, d2: dict, keys: list):
    """
    使用 all() 和生成器表达式比较字典中的指定键值
    """

    return all(d1.get(key) == d2.get(key) for key in keys)


def data2string(data: Any, char: str = ",") -> str:
    """
    将数据转换为字符串
    """

    if not isinstance(data, list):
        return str(data)
    return char.join([str(d) for d in data])


def preserved_order_sort(
    queryset: QuerySet,
    ordering_field: str,
    value_list: List,
    *,
    annotate_name: str = "_preserved_order",
    extra_order_by: List[str] | None = None,
):
    """
    使用 ORM 的 Case/When 注解实现安全的“按给定值顺序”排序，兼容跨表字段。

    Args:
        queryset: 原始查询集
        ordering_field: 排序字段，支持带 '-' 前缀表示倒序，如 '-strategy__risk_level'
        value_list: 期望的排序值列表（从小到大）
        annotate_name: 注解字段名，默认 '_preserved_order'
        extra_order_by: 附加的排序字段列表，用于二级排序，比如 ['-event_time']

    Returns:
        QuerySet: 已按指定顺序排序的查询集
    """

    from django.db.models import Case, IntegerField, Value, When

    if not ordering_field:
        return queryset

    desc = ordering_field.startswith("-")
    field = ordering_field.lstrip("-")

    whens = [When(**{field: val}, then=Value(pos)) for pos, val in enumerate(value_list)]
    preserved = Case(*whens, default=Value(-1), output_field=IntegerField())
    qs = queryset.annotate(**{annotate_name: preserved})

    orders = [f"-{annotate_name}" if desc else annotate_name]
    if extra_order_by:
        orders.extend(extra_order_by)
    return qs.order_by(*orders)


def validate_unique_keys(items: List[Any], key_field: str, error_msg: Union[str, Callable[[Any], str]] = ""):
    """
    通用列表去重校验器
    :param items: 字典列表或对象列表
    :param key_field: 用于判断唯一的字段名
    :param error_msg: 报错信息模板。
                      可以是字符串（会自动拼上重复值），
                      也可以是函数（接收重复值，返回完整的错误字符串）。
    """

    seen = set()
    for item in items:
        # 兼容 item 是字典(TypedDict) 或 对象(Pydantic Model) 的情况
        val = item.get(key_field) if isinstance(item, dict) else getattr(item, key_field, None)
        if val in seen:
            msg = error_msg(val) if callable(error_msg) else error_msg
            raise ValueError(msg)
        seen.add(val)
    return items
