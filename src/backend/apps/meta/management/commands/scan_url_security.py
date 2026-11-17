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
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the specific language
governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.meta.models import ResourceType, System
from core.utils.url_security import URLSecurityError, validate_request_url, validate_resource_path


class Command(BaseCommand):
    help = (
        "扫描存量 System.callback_url 与 ResourceType.path 是否命中 URL 安全校验规则"
        "（只读，不修改数据）；用于发布门禁：命中数必须为 0 或已逐条确认豁免"
    )

    def handle(self, *args, **options):
        problems = []

        # 1. 扫描系统回调地址（非空值需通过 URL 安全校验）
        for system in System.objects.exclude(callback_url__isnull=True).exclude(callback_url="").only(
            "system_id", "callback_url"
        ):
            try:
                validate_request_url(system.callback_url)
            except URLSecurityError as err:
                problems.append(f"[System] system_id={system.system_id} callback_url={system.callback_url!r} => {err}")

        # 2. 扫描资源类型路径形态（非空值需通过 path 形态校验）
        for resource_type in ResourceType.objects.exclude(path="").only(
            "system_id", "unique_id", "resource_type_id", "path"
        ):
            try:
                validate_resource_path(resource_type.path)
            except URLSecurityError as err:
                problems.append(
                    f"[ResourceType] unique_id={resource_type.unique_id} path={resource_type.path!r} => {err}"
                )

        # 3. 扫描拼接后最终 URL（callback_url 非空系统的非空 path 组合，拼接方式与线上 resource_request_url 一致）
        systems_with_callback = {
            system.system_id: system
            for system in System.objects.exclude(callback_url__isnull=True).exclude(callback_url="").only(
                "system_id", "callback_url"
            )
        }
        for resource_type in ResourceType.objects.exclude(path="").only(
            "system_id", "unique_id", "resource_type_id", "path"
        ):
            system = systems_with_callback.get(resource_type.system_id)
            if not system:
                continue
            url = resource_type.resource_request_url(system)
            try:
                validate_request_url(url)
            except URLSecurityError as err:
                problems.append(f"[Combined] unique_id={resource_type.unique_id} url={url!r} => {err}")

        if problems:
            raise CommandError(
                f"URL 安全校验存量扫描命中 {len(problems)} 条（发布门禁要求清零或逐条确认豁免）：\n"
                + "\n".join(problems)
            )
        self.stdout.write(self.style.SUCCESS("URL 安全校验存量扫描通过：0 命中"))
