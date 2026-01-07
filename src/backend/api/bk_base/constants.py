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

UNSUPPORTED_CODE = "1500404"


class AuthType(TextChoices):
    """
    认证方式
    """

    USER = "user", gettext_lazy("用户")
    TOKEN = "token", gettext_lazy("Token")


class StorageType(TextChoices):
    """
    存储类型
    """

    HDFS = "hdfs", gettext_lazy("HDFS")
    DORIS = "doris", gettext_lazy("Doris")


class UserAuthActionEnum(TextChoices):
    """
    用户认证行为枚举
    """

    RT_QUERY = "result_table.query_data", gettext_lazy("结果表查询")


class BkBaseFieldType(TextChoices):
    """
    BKBase 字段类型枚举
    用于报告聚合函数接口的字段类型匹配
    """

    INT = "int", gettext_lazy("整数")
    LONG = "long", gettext_lazy("长整数")
    FLOAT = "float", gettext_lazy("浮点数")
    DOUBLE = "double", gettext_lazy("双精度浮点数")
    STRING = "string", gettext_lazy("字符串")
    TIMESTAMP = "timestamp", gettext_lazy("时间戳")
    TEXT = "text", gettext_lazy("文本")
