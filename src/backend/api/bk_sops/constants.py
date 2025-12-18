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

from django.utils import timezone
from rest_framework.settings import api_settings


class SOpsDatetime(str):
    """
    标准运维时间格式
    """

    format = "%Y-%m-%d %H:%M:%S %z"

    def __new__(cls, time_str: str):
        if not time_str:
            return ""
        try:
            return (
                datetime.datetime.strptime(time_str, cls.format)
                .astimezone(timezone.get_current_timezone())
                .strftime(api_settings.DATETIME_FORMAT)
            )
        except (ValueError, TypeError):
            return time_str
