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
import re

from django.utils.translation import gettext_lazy

from core.choices import TextChoices

IAM_MANAGER_ROLE = "members"
IAM_SYSTEM_BATCH_SIZE = 10
IAM_ACTION_BATCH_SIZE = 100
IAM_RESOURCE_BATCH_SIZE = 100

PAAS_APP_BATCH_SIZE = 20

FETCH_INSTANCE_SCHEMA_METHOD = "fetch_resource_type_schema"
FETCH_INSTANCE_SCHEMA_CACHE_TIMEOUT = 300

GET_APP_INFO_CACHE_TIMEOUT = 300

LIST_USERS_LOOKUP_FIELD = "username"
LIST_USER_PAGE = 1
LIST_USER_PAGE_SIZE = 100
LIST_USER_FIELDS = "id,username,display_name"
ALLOWED_LIST_USER_FIELDS = ["id", "username", "display_name"]
RETRIEVE_USER_FIELDS = "id,username,display_name,departments,status,leader,staff_status,extras"
RETRIEVE_USER_TIMEOUT = 300

SENSITIVE_REPLACE_VALUE = "******"

TAG_NAME_REGEXP = re.compile(r"^[\w\u4e00-\u9fa5-_]+$")


class SensitiveUserData:
    SYSTEM_ID = os.getenv("BKAPP_SENSITIVE_USER_DATA_SYSTEM_ID", "bk_usermgr")
    RESOURCE_ID = os.getenv("BKAPP_SENSITIVE_USER_DATA_RESOURCE_ID", "user")


class SensitiveResourceTypeEnum(TextChoices):
    ACTION = "sensitive_action_object", gettext_lazy("敏感对象(操作)")
    RESOURCE = "sensitive_resource_object", gettext_lazy("敏感对象(资源)")


DEFAULT_ES_SOURCE_TYPE = [
    {"id": "dba", "name": gettext_lazy("DBA托管")},
    {"id": "qcloud", "name": gettext_lazy("腾讯云")},
]

DEFAULT_DURATION_TIME = [
    {"id": "1", "name": gettext_lazy("1天"), "default": False},
    {"id": "3", "name": gettext_lazy("3天"), "default": False},
    {"id": "7", "name": gettext_lazy("7天"), "default": True},
    {"id": "14", "name": gettext_lazy("14天"), "default": False},
    {"id": "30", "name": gettext_lazy("30天"), "default": False},
]

DEFAULT_DATA_DELIMITER = [
    {"id": "|", "name": gettext_lazy("竖线(|)")},
    {"id": ",", "name": gettext_lazy("逗号(,)")},
    {"id": "`", "name": gettext_lazy("反引号(`)")},
    {"id": " ", "name": gettext_lazy("空格")},
    {"id": ";", "name": gettext_lazy("分号(;)")},
]

DEFAULT_DATA_ENCODING = [
    {"id": "UTF-8", "name": "UTF-8"},
]

GLOBAL_CONFIG_LEVEL_INSTANCE = "global"


class ConfigLevelChoices(TextChoices):
    GLOBAL = "global", gettext_lazy("全局配置")
    BIZ = "biz", gettext_lazy("业务配置")
    SYSTEM = "system", gettext_lazy("应用配置")
    NAMESPACE = "namespace", gettext_lazy("命名空间")


class OrderTypeChoices(TextChoices):
    ASC = "asc", gettext_lazy("升序")
    DESC = "desc", gettext_lazy("降序")


class SpaceType(TextChoices):
    """空间类型"""

    BIZ = "bkcc", gettext_lazy("业务")
    BCS = "bcs", gettext_lazy("BCS项目")
    BKCI = "bkci", gettext_lazy("研发项目")
    BKDEVOPS = "bkdevops", gettext_lazy("蓝盾项目")
    UNKNOWN = "unknown", gettext_lazy("未知")


class ContainerCollectorType(TextChoices):
    CONTAINER = "container_log_config", gettext_lazy("Container")
    NODE = "node_log_config", gettext_lazy("Node")
    STDOUT = "std_log_config", gettext_lazy("标准输出")


class EtlConfigEnum(TextChoices):
    BK_LOG_JSON = "bk_log_json", gettext_lazy("JSON")
    BK_LOG_DELIMITER = "bk_log_delimiter", gettext_lazy("分隔符")
    BK_LOG_REGEXP = "bk_log_regexp", gettext_lazy("正则")
    BK_BASE_JSON = "bk_base_json", gettext_lazy("计算平台JSON")


class CollectorParamConditionTypeEnum(TextChoices):
    NONE = "none", gettext_lazy("不过滤")
    MATCH = "match", gettext_lazy("字符串过滤")
    SEPARATOR = "separator", gettext_lazy("分隔符过滤")


class CollectorParamConditionMatchType(TextChoices):
    INCLUDE = "include", gettext_lazy("保留匹配字符串")
