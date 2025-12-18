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

from django.db import models
from django.utils.translation import gettext_lazy

from core.models import SoftDeleteModel, UUIDField
from services.web.analyze.constants import ControlTypeChoices


class Control(SoftDeleteModel):
    """
    Control is an instance of Control Type
    """

    control_id = UUIDField(gettext_lazy("Control ID"), primary_key=True)
    control_name = models.CharField(gettext_lazy("Control Name"), max_length=64)
    control_type_id = models.CharField(
        gettext_lazy("Control Type ID"), max_length=64, choices=ControlTypeChoices.choices
    )
    priority_index = models.IntegerField(gettext_lazy("Priority Index"), default=0)

    class Meta:
        verbose_name = gettext_lazy("Control")
        verbose_name_plural = verbose_name
        ordering = ["-priority_index", "control_type_id", "control_id"]
        unique_together = ["control_type_id", "control_name"]


class ControlVersion(SoftDeleteModel):
    """
    Control Version
    """

    control_id = models.CharField(gettext_lazy("Control ID"), max_length=64)
    control_version = models.IntegerField(gettext_lazy("Control Version"))
    input_config = models.JSONField(gettext_lazy("Input Config"), default=dict, null=True, blank=True)
    output_config = models.JSONField(gettext_lazy("Output Config"), default=dict, null=True, blank=True)
    variable_config = models.JSONField(gettext_lazy("Variable Config"), default=dict, null=True, blank=True)
    extra_config = models.JSONField(gettext_lazy("Extra Config"), default=dict, null=True, blank=True)

    class Meta:
        verbose_name = gettext_lazy("Control Version")
        verbose_name_plural = verbose_name
        ordering = ["control_id", "-control_version"]
        unique_together = [["control_id", "control_version"]]
