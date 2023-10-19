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

from apps.feature.constants import FeatureStatusChoices


class FeatureToggle(models.Model):
    """特性开关"""

    feature_id = models.CharField(gettext_lazy("特性开关ID"), max_length=64, primary_key=True)
    alias = models.CharField(gettext_lazy("特性开关别名"), max_length=64, null=True, blank=True)
    status = models.CharField(
        gettext_lazy("特性开关status"),
        max_length=32,
        choices=FeatureStatusChoices.choices,
        default=FeatureStatusChoices.DENY.value,
    )
    is_enable_view = models.BooleanField(gettext_lazy("是否在前端展示"), default=True)
    config = models.JSONField(gettext_lazy("特性开关配置"), null=True, blank=True)

    class Meta:
        verbose_name = gettext_lazy("特性开关")
        verbose_name_plural = verbose_name
        ordering = ["feature_id"]
