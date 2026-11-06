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
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import os
import uuid

from django.db import migrations, models

PRESET_PA_NAME = "【内置】BKSEC安全工单发单"
PROCESS_APPLICATION = "process_application"
PLATFORM_BINDING = "platform_binding"
ALL_SCENES = "all_scenes"


def bind_builtin_pa_all_scenes(apps, pa):
    """内置套餐绑成平台级，全部场景可见。"""

    resource_binding = apps.get_model("scene", "ResourceBinding")
    binding = resource_binding.objects.filter(
        resource_type=PROCESS_APPLICATION,
        resource_id=str(pa.id),
    ).first()
    if binding is None:
        resource_binding.objects.create(
            resource_type=PROCESS_APPLICATION,
            resource_id=str(pa.id),
            binding_type=PLATFORM_BINDING,
            visibility_type=ALL_SCENES,
        )
        return
    if binding.binding_type != PLATFORM_BINDING or binding.visibility_type != ALL_SCENES:
        binding.binding_type = PLATFORM_BINDING
        binding.visibility_type = ALL_SCENES
        binding.save(update_fields=["binding_type", "visibility_type"])


def create_builtin_pa(apps, schema_editor):
    """
    迁移时按 BKAPP_BKSEC_SOPS_TEMPLATE_ID 补齐内置套餐，并绑成平台级、全部场景可见。

    未配置或不是整数时跳过，迁移仍然成功。已有同模板 ID 的内置套餐则不新建，
    只补绑定，也不修改其他套餐的模板 ID。运行时还会再补一次，环境变量后配或更换模板 ID 仍然有效。
    """
    raw = os.environ.get("BKAPP_BKSEC_SOPS_TEMPLATE_ID")
    if not raw:
        return
    try:
        template_id = int(raw)
    except (TypeError, ValueError):
        return
    process_application = apps.get_model("risk", "ProcessApplication")
    existing = process_application.objects.filter(is_builtin=True, sops_template_id=template_id).order_by("-id").first()
    if existing is not None:
        bind_builtin_pa_all_scenes(apps, existing)
        return
    pa = process_application.objects.create(
        uniq_id=uuid.uuid4().hex,
        name=PRESET_PA_NAME,
        sops_template_id=template_id,
        need_approve=False,
        is_enabled=True,
        is_builtin=True,
        is_deleted=False,
    )
    bind_builtin_pa_all_scenes(apps, pa)


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0066_alter_processapplication_approve_service_id_and_more"),
        ("scene", "0014_scene_permission_application"),
    ]

    operations = [
        migrations.AddField(
            model_name="processapplication",
            name="is_builtin",
            field=models.BooleanField(
                default=False,
                help_text="系统内置套餐（如 BKSEC 发单），请勿删除或停用",
                verbose_name="Is Builtin",
            ),
        ),
        migrations.AddField(
            model_name="riskrule",
            name="auto_strategy_id",
            field=models.BigIntegerField(
                blank=True,
                db_index=True,
                help_text="策略 BKSEC 发单自动创建时记录来源策略 ID，非空表示系统自动规则",
                null=True,
                verbose_name="Auto Created By Strategy",
            ),
        ),
        migrations.AddField(
            model_name="ticketnode",
            name="is_test",
            field=models.BooleanField(db_index=True, default=False, verbose_name="Is Test"),
        ),
        migrations.RunPython(create_builtin_pa, migrations.RunPython.noop),
    ]
