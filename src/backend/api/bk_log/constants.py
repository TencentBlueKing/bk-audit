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

DEFAULT_RETENTION = 14
DEFAULT_STORAGE_REPLIES = 1

CLUSTER_NAME_EN_REGEX = r"^[A-Za-z0-9_]+$"

BK_AUDIT_TAGS = ["BK-AUDIT"]

INDEX_SET_ID = "index_set_id"

EMPTY_PASSWORD_PLACEHOLDER = "******"


class VisibleEnum(TextChoices):
    # 当前业务可见
    CURRENT_BIZ = "current_biz", gettext_lazy("当前业务")
    # 多业务可见
    MULTI_BIZ = "multi_biz", gettext_lazy("多业务")
    # 全业务
    ALL_BIZ = "all_biz", gettext_lazy("全业务")
    # 业务属性可见
    BIZ_ATTR = "biz_attr", gettext_lazy("业务属性")


class InstanceTypeEnum(TextChoices):
    HOST = "host", gettext_lazy("主机")


class TemplateTypeChoices(TextChoices):
    SERVICE_TEMPLATE = "SERVICE_TEMPLATE", gettext_lazy("服务模板")
    SET_TEMPLATE = "SET_TEMPLATE", gettext_lazy("集群模版")


DEFAULT_VISIBLE_CONFIG = {"visible_type": "current_biz", "visible_bk_biz": [], "bk_biz_labels": {}}

PARTITION_ERROR_CODE = "3631402"
