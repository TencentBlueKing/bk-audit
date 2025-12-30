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
from django.db import migrations

from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.fields import SNAPSHOT_USER_INFO
from services.web.log_subscription.constants import (
    GLOBAL_FIELD_BLACKLIST_SOURCE_ID,
    LOG_SUBSCRIPTION_FIELD_BLACKLIST_KEY,
)


def init_field_blacklist(*args, **kwargs):
    """
    初始化日志订阅字段黑名单配置

    默认将 SNAPSHOT_USER_INFO 字段作为全局黑名单
    """
    blacklist_config = {
        GLOBAL_FIELD_BLACKLIST_SOURCE_ID: [SNAPSHOT_USER_INFO.field_name],
    }
    GlobalMetaConfig.set(
        config_key=LOG_SUBSCRIPTION_FIELD_BLACKLIST_KEY,
        config_value=blacklist_config,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("log_subscription", "0002_logdatasource_fields"),
        ("meta", "0001_initial"),
    ]

    operations = [migrations.RunPython(init_field_blacklist)]
