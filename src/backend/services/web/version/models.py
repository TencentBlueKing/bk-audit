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


class VersionLog(models.Model):
    version = models.CharField(gettext_lazy("版本号"), max_length=32, primary_key=True)
    content = models.TextField(gettext_lazy("版本日志"), blank=True, null=True)
    release_at = models.DateField(gettext_lazy("发布时间"))

    class Meta:
        verbose_name = gettext_lazy("版本日志")
        verbose_name_plural = verbose_name
        ordering = ["-release_at"]


class VersionLogVisit(models.Model):
    version = models.CharField(gettext_lazy("版本号"), max_length=32)
    username = models.CharField(gettext_lazy("用户名"), max_length=64)
    visit_at = models.DateTimeField(gettext_lazy("查看时间"), auto_now=True)

    class Meta:
        verbose_name = gettext_lazy("版本日志访问记录")
        verbose_name_plural = verbose_name
        unique_together = [["version", "username"]]
        ordering = ["username", "-visit_at"]
