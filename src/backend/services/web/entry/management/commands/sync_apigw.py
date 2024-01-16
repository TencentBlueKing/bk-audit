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

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        if not settings.BKAUDIT_API_HOST:
            return

        definition_path = "support-files/apigw/definition.yaml"
        resources_path = "support-files/apigw/resources.yaml"

        call_command("sync_apigw_config", f"--file={definition_path}")
        call_command("sync_apigw_stage", f"--file={definition_path}")
        call_command("sync_apigw_resources", f"--file={resources_path}")
        call_command("create_version_and_release_apigw", f"--file={definition_path}")
        call_command("fetch_apigw_public_key")
