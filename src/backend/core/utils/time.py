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

import arrow
from arrow import Arrow
from blueapps.utils.logger import logger
from dateutil.tz import tzutc
from django.utils import timezone
from rest_framework.settings import api_settings


def mstimestamp_to_date_string(timestamp: int) -> str:
    """毫秒时间戳转日期"""
    return (
        datetime.datetime.fromtimestamp(timestamp / 1000)
        .astimezone(timezone.get_default_timezone())
        .strftime(api_settings.DATETIME_FORMAT)
    )


def parse_datetime(date_string: str) -> Arrow:
    """
    解析时间:若无时区则默认为本地时区
    """

    date = arrow.get(date_string)
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
