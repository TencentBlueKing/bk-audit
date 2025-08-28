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


class FeatureStatusChoices(TextChoices):
    DENY = "deny", gettext_lazy("已关闭")
    STAG = "stag", gettext_lazy("测试环境")
    PROD = "prod", gettext_lazy("正式环境")
    AVAILABLE = "available", gettext_lazy("已启用")


class FeatureTypeChoices(TextChoices):
    """
    Feature Type
    """

    BKBASE_AIOPS = "bkbase_aiops", gettext_lazy("AIOPS")
    BKLOG_OTLP = "bklog_otlp", gettext_lazy("OTLP")
    WATERMARK = "watermark", gettext_lazy("水印")
    BKVISION = "bkvision", gettext_lazy("BKVision")
    BKNOTICE = "bknotice", gettext_lazy("通知")
    BKBASE_DATA_SOURCE = "bkbase_data_source", gettext_lazy("数据源")
    STORAGE_EDIT = "storage_edit", gettext_lazy("存储编辑")
    ENABLE_DORIS = "enable_doris", gettext_lazy("启用 Doris")
    CHECK_BKVISION_SHARE_PERMISSION = "check_bkvision_share_permission", gettext_lazy("校验BKVision分享权限")
