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

from django.utils.translation import gettext_lazy

from core.choices import TextChoices

DEFAULT_JSON_EXPAND_LEVEL = 2
DEFAULT_JSON_EXPAND_SEPARATOR = "/"

DEFAULT_NGETTEXT_COUNT = 1


class TimeEnum(Enum):
    """
    时间枚举
    """

    ONE_SECOND: int = 1
    ONE_MINUTE_SECOND: int = ONE_SECOND * 60
    FIVE_MINUTE_SECOND: int = ONE_MINUTE_SECOND * 5
    ONE_HOUR_SECOND: int = ONE_MINUTE_SECOND * 60
    ONE_DAY_SECOND: int = ONE_HOUR_SECOND * 24
    ONE_YEAR_SECOND: int = ONE_DAY_SECOND * 365


class ErrorCode(Enum):
    """
    ESB异常代码
    """

    ESB_API_NOT_FORBIDDEN = 20102  # API没有权限
    ESB_API_FORMAT_ERROR = 1306201  # API后端返回格式异常
    IAM_NOT_PERMISSION = "9900403"


class OrderTypeChoices(TextChoices):
    ASC = "asc", gettext_lazy("升序")
    DESC = "desc", gettext_lazy("降序")


# 文件下载流式传输分片大小(bytes)
FILE_DOWNLOAD_CHUNK_SIZE = 8096
