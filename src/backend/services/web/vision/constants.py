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
from iam.model.models import ResourceType

from core.choices import TextChoices


class KeyVariable(TextChoices):
    """
    关键变量
    """

    DEPARTMENT = "dept", gettext_lazy("组织架构")
    DEPARTMENT_NAME = "dept_name", gettext_lazy("组织架构")
    TAG = "tag", gettext_lazy("标签")
    SYSTEM_ID = "system_id", gettext_lazy("系统ID")


class PanelType(TextChoices):
    """
    组件类型
    """

    ACTION = "Action", gettext_lazy("筛选")


PANEL = ResourceType(
    id="panel",
    name=None,
    name_en=None,
    description=None,
    description_en=None,
    parents=None,
    provider_config=None,
    version=None,
)
