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
from typing import Any

from pypika.functions import Count
from pypika.terms import Function


class DisCount(Count):
    """
    去重计数
    """

    def __init__(self, param, alias=None):
        super().__init__(param, alias=alias)
        self.distinct()


class ConcatWs(Function):
    """
    CONCAT_WS函数
    """

    def __init__(self, separator, *args):
        super(ConcatWs, self).__init__("CONCAT_WS", separator, *args)


class DateTrunc(Function):
    """日期截断函数"""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__("DATE_TRUNC", *args, **kwargs)


class FromUnixTime(Function):
    """Unix时间戳转换为日期函数"""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__("FROM_UNIXTIME", *args, **kwargs)
