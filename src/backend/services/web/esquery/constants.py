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

from django.utils.translation import gettext_lazy

from core.choices import TextChoices

DEFAULT_TIMEDELTA = 7
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10

ES_MAX_LIMIT = 10000

SORT_ASC = "asc"
SORT_DESC = "desc"

DEFAULT_SORT_LIST = [["dtEventTimeStamp", SORT_DESC], ["gseIndex", SORT_DESC], ["iterationIndex", SORT_DESC]]


class AccessTypeChoices(TextChoices):
    WEB = "0", gettext_lazy("WebUI")
    API = "1", gettext_lazy("API")
    CONSOLE = "2", gettext_lazy("Console")
    OTHER = "-1", gettext_lazy("Other")


class UserIdentifyTypeChoices(TextChoices):
    PERSONAL = "0", gettext_lazy("个人账号")
    PLATFORM = "1", gettext_lazy("平台账号")


class ResultCodeChoices(TextChoices):
    SUCCESS = "0", gettext_lazy("成功")
    FAILED = "-1", gettext_lazy("其他")
