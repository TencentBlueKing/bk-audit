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

from django.contrib import admin
from django.utils.translation import gettext_lazy

from core.utils.data import choices_to_items
from services.web.analyze.constants import ControlTypeChoices
from services.web.analyze.models import Control, ControlVersion


@admin.register(Control)
class ControlAdmin(admin.ModelAdmin):
    list_display = ["control_id", "control_name", "control_type_id", "is_deleted"]
    list_filter = ["control_type_id", "is_deleted"]
    ordering = ["-control_id"]


@admin.register(ControlVersion)
class ControlVersionAdmin(admin.ModelAdmin):
    list_display = ["id", "control_name", "control_id", "control_version", "control_type_name", "is_deleted"]
    list_filter = ["is_deleted"]
    ordering = ["control_id", "-control_version"]

    @admin.display(description=gettext_lazy("Control Name"))
    def control_name(self, inst: Control):
        return Control.objects.get(control_id=inst.control_id).control_name

    @admin.display(description=gettext_lazy("Control Type"))
    def control_type_name(self, inst: Control):
        control_type_id = Control.objects.get(control_id=inst.control_id).control_type_id
        return choices_to_items(ControlTypeChoices).get(control_type_id, control_type_id)
