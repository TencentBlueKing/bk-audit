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
from enum import Enum
from types import DynamicClassAttribute
from typing import Union

from django.db.models import Choices
from django.db.models import IntegerChoices as DjangoIntegerChoices
from django.db.models import TextChoices as DjangoTextChoices


class ChoiceGetLabelMixin(Choices):
    @classmethod
    def get_label(cls, key: Union[int, str]) -> Union[int, str]:
        for val, label in cls.choices:
            if val == key:
                return label
        return key


class TextChoices(DjangoTextChoices, ChoiceGetLabelMixin):
    @DynamicClassAttribute
    def value(self) -> str:
        return str(self._value_)


class IntegerChoices(DjangoIntegerChoices, ChoiceGetLabelMixin):
    @DynamicClassAttribute
    def value(self) -> int:
        return int(self._value_)


# 存放已注册的枚举类
_default = {}


def register_choices(name: str = None):
    """
    注册choices类型的配置
    """

    def decorator(cls):
        nonlocal name
        # 如果装饰的为类，则取类名
        if not name:
            name = cls.__name__
        # 将列表转换为Enum类型
        if isinstance(cls, list):
            cls = Enum(name, names=cls)
        # 检测是否已经注册
        if name in _default:
            raise ValueError(f"{name} has already been registered.")
        _default[name] = cls
        return cls

    return decorator


def list_registered_choices():
    """获得已经注册的所有choicesEnum ."""
    return _default
