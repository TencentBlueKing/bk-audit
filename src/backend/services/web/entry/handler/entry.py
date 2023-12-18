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

import os

from bk_resource import resource
from blueapps.account.conf import ConfFixture  # noqa
from blueapps.utils.logger import logger
from django.conf import settings
from django.utils.translation import gettext

from apps.bk_crypto.crypto import asymmetric_cipher
from apps.feature.handlers import FeatureHandler
from apps.meta.models import GlobalMetaConfig
from services.web.entry.constants import (
    DEFAULT_QUERY_STRING_HELP_ENV_KEY,
    DEFAULT_QUERY_STRING_HELP_KEY,
    DEFAULT_SCHEMA_HELP,
    DEFAULT_SCHEMA_HELP_KEY,
    DEFAULT_WEB_COPYRIGHT,
    DEFAULT_WEB_COPYRIGHT_KEY,
    DEFAULT_WEB_FOOTER,
    DEFAULT_WEB_FOOTER_KEY,
    DEFAULT_WEB_SITE_TITLE,
    DEFAULT_WEB_SITE_TITLE_KEY,
    DEFAULT_WEB_TITLE,
    DEFAULT_WEB_TITLE_KEY,
)


class EntryHandler(object):
    """
    EntryHandler
    """

    @classmethod
    def entry(cls, request) -> dict:
        static_url = settings.STATIC_URL.replace("http://", "//")
        app_subdomains = os.getenv("BKAPP_ENGINE_APP_DEFAULT_SUBDOMAINS", None)
        if app_subdomains:
            static_url = "//%s/static/" % app_subdomains.split(";")[0]

        # 特性开关
        feature_toggle = {}

        # 平台管理员
        if request.user.is_authenticated:
            manage_actions = "list_storage,list_sensitive_object"
            results = resource.permission.check_permission(action_ids=manage_actions)
            super_manager = any(results.values())
        else:
            super_manager = False

        data = {
            # 应用信息
            "app_code": settings.APP_CODE,
            "site_url": settings.SITE_URL,
            # 用户信息
            "username": request.user.username,
            "super_manager": super_manager,
            # 远程静态资源url
            "remote_static_url": settings.REMOTE_STATIC_URL,
            # 静态资源
            "static_url": static_url,
            "static_version": settings.STATIC_VERSION,
            # 登录跳转链接
            "login_url": ConfFixture.LOGIN_URL,
            # 特性开关
            "feature_toggle": feature_toggle,
            # TAM
            "aegis_id": settings.AEGIS_ID,
            # 页面信息
            "title": cls.get_title(),
            "footer": cls.get_footer(),
            "copyright": cls.get_copyright(),
            "site_title": cls.get_site_title(),
            "help_info": {"query_string": cls.get_query_help(), "schema": cls.get_schema_help()},
            # 语言
            "language": {
                "available": [{"id": lang_code, "name": desc} for lang_code, desc in settings.LANGUAGES],
                "name": settings.LANGUAGE_COOKIE_NAME,
                "domain": settings.LANGUAGE_COOKIE_DOMAIN,
            },
            # 业务
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            # 加密算法
            "public_key": asymmetric_cipher.export_public_key(),
            "encryption_algorithm": settings.BKCRYPTO["ASYMMETRIC_CIPHER_TYPE"],
        }
        return data

    @classmethod
    def get_title(cls):
        return gettext(GlobalMetaConfig.get(DEFAULT_WEB_TITLE_KEY, default="")) or DEFAULT_WEB_TITLE

    @classmethod
    def get_footer(cls):
        footer = GlobalMetaConfig.get(DEFAULT_WEB_FOOTER_KEY, default=[])
        if not footer:
            return DEFAULT_WEB_FOOTER
        for item in footer:
            item["text"] = gettext(item.get("text", ""))
        return footer

    @classmethod
    def get_copyright(cls):
        copyright_msg = GlobalMetaConfig.get(DEFAULT_WEB_COPYRIGHT_KEY, default=DEFAULT_WEB_COPYRIGHT)
        version = cls.get_version()
        return f"{copyright_msg} {version}" if version else copyright_msg

    @classmethod
    def get_site_title(cls):
        return GlobalMetaConfig.get(DEFAULT_WEB_SITE_TITLE_KEY, default=DEFAULT_WEB_SITE_TITLE)

    @classmethod
    def get_version(cls):
        file = os.path.join(settings.BASE_DIR, "VERSION")
        try:
            with open(file, "r") as file:
                return file.read().strip() or str()
        except Exception as err:  # NOCC:broad-except(需要处理所有异常)
            logger.exception(f"GetVersion Failed => {err}")
            return str()

    @classmethod
    def get_query_help(cls):
        return GlobalMetaConfig.get(
            DEFAULT_QUERY_STRING_HELP_KEY,
            default=os.getenv(
                DEFAULT_QUERY_STRING_HELP_ENV_KEY,
                (
                    "https://bk.tencent.com/docs/markdown/ZH/LogSearch/4.6"
                    "/UserGuide/ProductFeatures/data-visualization/query_string.md"
                ),
            ),
        )

    @classmethod
    def get_schema_help(cls):
        return GlobalMetaConfig.get(DEFAULT_SCHEMA_HELP_KEY, default=DEFAULT_SCHEMA_HELP)


class WatermarkFeature:
    @property
    def available(self) -> bool:
        if FeatureHandler("watermark").check():
            return True
        return False
