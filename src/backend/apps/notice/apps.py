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

from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.utils.translation import gettext_lazy

from apps.notice.constants import ADMIN_NOTICE_GROUP_ID
from core.tenant import get_bk_tenant_id, use_multi_tenant_mode
from core.utils.environ import get_env_or_raise


class NoticeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notice"
    verbose_name = gettext_lazy("Notice")

    def ready(self):
        post_migrate.connect(self._init_system_admin_notice, self)
        self._patch_bk_notice_sdk_tenant_header()

    def _patch_bk_notice_sdk_tenant_header(self):
        """为 bk_notice_sdk 的出站请求注入多租户 Header。
        """
        if not use_multi_tenant_mode():
            return

        from bkapi.bk_notice.client import Client as BkNoticeClient

        tenant_id = get_bk_tenant_id()
        if not tenant_id:
            return

        original_handle_request = BkNoticeClient.handle_request

        def patched_handle_request(self, operation, context):
            headers = context.get("headers") or {}
            if "X-Bk-Tenant-Id" not in headers:
                headers["X-Bk-Tenant-Id"] = tenant_id
                context["headers"] = headers
            return original_handle_request(self, operation, context)

        BkNoticeClient.handle_request = patched_handle_request

    def _init_system_admin_notice(self, *args, **kwargs):
        """
        初始化系统管理员的通知组
        """

        from apps.notice.constants import (
            ADMIN_NOTICE_GROUP_NAME,
            get_default_notice_config,
        )
        from apps.notice.models import NoticeGroup

        NoticeGroup.objects.get_or_create(
            group_id=ADMIN_NOTICE_GROUP_ID,
            defaults={
                "group_name": ADMIN_NOTICE_GROUP_NAME,
                "group_member": [u for u in get_env_or_raise("BKAPP_ADMIN_USERNAMES").split(",") if u],
                "notice_config": get_default_notice_config(),
            },
        )
