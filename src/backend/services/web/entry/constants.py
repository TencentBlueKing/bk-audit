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

from django.utils.translation import gettext_lazy

from core.choices import TextChoices

HEALTHZ_SPAN_NAME = "Healthz"
HEALTHZ_THROTTLE_SCOPE = "10/m"


class WebLinkEnum(TextChoices):
    WEB_LINK = "link", gettext_lazy("超链接")


INIT_ES_FISHED_KEY = "init_es_finished_check"
INIT_DORIS_FISHED_KEY = "init_doris_finished_check"
INIT_REDIS_FISHED_KEY = "init_redis_finished_check"
INIT_PLUGIN_FISHED_KEY = "init_plugin_finished_check"
INIT_SNAPSHOT_FINISHED_KEY = "init_snapshot_finished_check"
INIT_EVENT_FINISHED_KEY = "init_event_finished_check"
INIT_FIELDS_FINISHED_KEY = "init_fields_finished_check"

DEFAULT_QUERY_STRING_HELP_KEY = "query_string_help"
DEFAULT_QUERY_STRING_HELP_ENV_KEY = "BKAPP_QUERY_STRING_HELP"

DEFAULT_SCHEMA_HELP_KEY = "schema_help"
DEFAULT_SCHEMA_HELP = (
    "https://github.com/TencentBlueKing/iam-python-sdk/blob/master/docs/usage.md"
    "#31-resourceprovider-%E7%9A%84%E5%AE%9A%E4%B9%89"
)

TENCENT_WEB_FOOTER = [
    {
        "type": WebLinkEnum.WEB_LINK.value,
        "type_description": WebLinkEnum.WEB_LINK.label,
        "text": gettext_lazy("联系BK助手"),
        "url": "",
    },
    {
        "type": WebLinkEnum.WEB_LINK.value,
        "type_description": WebLinkEnum.WEB_LINK.label,
        "text": gettext_lazy("蓝鲸桌面"),
        "url": "",
    },
]

# IAM WEB 访问地址
IAM_WEB_URL_KEY = "iam_web_url"
# 互娱应用系统和敏感操作安全管理规范访问地址
IEG_STD_OP_DOC_URL_KEY = "ieg_std_op_doc_url"
# bkbase WEB 访问地址
BKBASE_WEB_URL_KEY = "bkbase_web_url"
