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

from apps.bk_crypto.crypto import asymmetric_cipher
from apps.feature.constants import FeatureTypeChoices
from apps.feature.handlers import FeatureHandler
from apps.meta.models import GlobalMetaConfig
from services.web.entry.constants import (
    AI_PRACTICES_KEY,
    BKBASE_WEB_URL_KEY,
    BKVISION_WEB_URL_KEY,
    DEFAULT_AI_PRACTICES,
    DEFAULT_QUERY_STRING_HELP_ENV_KEY,
    DEFAULT_QUERY_STRING_HELP_KEY,
    DEFAULT_SCHEMA_HELP,
    DEFAULT_SCHEMA_HELP_KEY,
    IAM_WEB_URL_KEY,
    IEG_STD_OP_DOC_URL_KEY,
    PERMISSION_MODEL_IWIKI_URL_KEY,
    SEARCH_RULE_IWIKI_URL_KEY,
    V3_SYSTEM_CREATE_URL_KEY,
    VISION_SHARE_PERMISSION_URL_KEY,
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
        manage_actions = "list_storage,list_sensitive_object"
        results = resource.permission.check_permission(action_ids=manage_actions)
        super_manager = any(results.values())

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
            "help_info": {
                "query_string": cls.get_query_help(),
                "schema": cls.get_schema_help(),
                "ai_practices": GlobalMetaConfig.get(AI_PRACTICES_KEY, default=DEFAULT_AI_PRACTICES),
            },
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
            # 全局配置
            "shared_res_url": settings.BK_SHARED_RES_URL,
            "version": cls.get_version(),
            # 系统诊断
            "system_diagnosis": {
                "iam_web_url": GlobalMetaConfig.get(IAM_WEB_URL_KEY, default=""),
                "ieg_std_op_doc_url": GlobalMetaConfig.get(IEG_STD_OP_DOC_URL_KEY, default=""),
            },
            # 工具
            "tool": {"vision_share_permission_url": GlobalMetaConfig.get(VISION_SHARE_PERMISSION_URL_KEY, default="")},
            # 三方系统地址
            "third_party_system": {
                "bkbase_web_url": GlobalMetaConfig.get(BKBASE_WEB_URL_KEY, default=""),
                "v3_system_create_url": GlobalMetaConfig.get(V3_SYSTEM_CREATE_URL_KEY, default=""),
                "bkvision_web_url": GlobalMetaConfig.get(BKVISION_WEB_URL_KEY, default=""),
            },
            # 三方文档地址
            "third_doc_url": {
                "search_rule_iwiki_url": GlobalMetaConfig.get(SEARCH_RULE_IWIKI_URL_KEY, default=""),
                "permission_model_iwiki_url": GlobalMetaConfig.get(PERMISSION_MODEL_IWIKI_URL_KEY, default=""),
            },
            # metric
            "metric": {"metric_report_trace_url": settings.METRIC_REPORT_TRACE_URL},
            # 给前端注入租户ID和用户管理API域名
            "tenant_config": {
                'BK_TENANT_ID': getattr(settings, 'BK_TENANT_ID', 'tencent'),
                'BK_USER_WEB_APIGW_URL': cls.get_user_web_apigw_url(),
            },
        }
        return data

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

    @classmethod
    def get_user_web_apigw_url(cls):
        """
        获取人员选择器 API 的网关地址
        返回格式: BK_API_URL_TMPL + 网关环境
        """
        stage = os.getenv('BKPAAS_ENVIRONMENT', 'prod')
        base_url = settings.BK_API_URL_TMPL.format(api_name='bk-user-web').rstrip('/')
        # 如果是 http 则转换为 https
        if base_url.startswith('http://'):
            base_url = base_url.replace('http://', 'https://', 1)
        return f"{base_url}/{stage}"


class WatermarkFeature:
    @property
    def available(self) -> bool:
        if FeatureHandler(FeatureTypeChoices.WATERMARK).check():
            return True
        return False
