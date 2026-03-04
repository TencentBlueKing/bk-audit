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
import datetime
from datetime import timedelta
from typing import Optional, Union

import arrow
from arrow import Arrow
from blueapps.utils.logger import logger
from dateutil.tz import tzutc
from django.utils import timezone
from rest_framework.settings import api_settings


def ceil_to_second(dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    """将时间向上取整到秒

    如果存在微秒，则去掉微秒并加1秒，实现"向上取整"效果。
    主要用于 SQL 查询的时间范围，避免因微秒精度导致的边界丢失。

    Args:
        dt: datetime 对象

    Returns:
        向上取整后的 datetime 对象；如果输入为 None 则返回 None
    """
    if dt is None:
        return None

    # 如果有微秒，去掉微秒并加1秒
    if dt.microsecond:
        dt = dt.replace(microsecond=0) + timedelta(seconds=1)

    return dt


def mstimestamp_to_date_string(timestamp: int) -> str:
    """毫秒时间戳转日期"""
    return (
        datetime.datetime.fromtimestamp(timestamp / 1000)
        .astimezone(timezone.get_default_timezone())
        .strftime(api_settings.DATETIME_FORMAT)
    )


def parse_datetime(date_value: Union[str, int, float]) -> Arrow:
    """
    解析时间:若无时区则默认为本地时区
    """

    date = arrow.get(date_value)
    # 如果是时间戳，则直接返回，无需转换时区
    if isinstance(date_value, Union[int, float]):
        return date
    if isinstance(date.tzinfo, tzutc):
        date = date.replace(tzinfo=timezone.get_default_timezone())
    return date


def format_date_string(date_string: str, output_format: str = api_settings.DATETIME_FORMAT):
    """
    将时间转为不带时区的本地时间字符串
    :param date_string: 时间字符串，若不带时区，则默认为本地时区
    :param output_format: 输出格式
    """
    try:
        date = arrow.get(date_string)
        if isinstance(date.tzinfo, tzutc):
            date = date.replace(tzinfo=timezone.get_default_timezone())
        else:
            date = date.astimezone(timezone.get_default_timezone())
        return date.strftime(output_format)
    except Exception as err:  # pylint: disable=broad-except
        logger.exception(
            "[FormatDataStringFailed] DateString => %s; OutputFormat => %s; Err => %s", date_string, output_format, err
        )
        return date_string
