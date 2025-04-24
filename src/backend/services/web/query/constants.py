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

from apps.meta.utils.fields import (
    ACCESS_SOURCE_IP,
    ACCESS_TYPE,
    ACCESS_USER_AGENT,
    ACTION_ID,
    EVENT_CONTENT,
    EVENT_ID,
    EXTEND_DATA,
    INSTANCE_DATA,
    INSTANCE_ID,
    INSTANCE_NAME,
    INSTANCE_ORIGIN_DATA,
    LOG,
    REQUEST_ID,
    RESOURCE_TYPE_ID,
    RESULT_CODE,
    RESULT_CONTENT,
    SNAPSHOT_ACTION_INFO,
    SNAPSHOT_INSTANCE_DATA,
    SNAPSHOT_RESOURCE_TYPE_INFO,
    SYSTEM_ID,
    USER_IDENTIFY_TYPE,
    USERNAME,
)
from core.choices import TextChoices
from core.constants import OrderTypeChoices
from services.web.query.utils.search_config import (
    CollectorSearchConfig,
    FieldSearchConfig,
    QueryConditionOperator,
)

DEFAULT_TIMEDELTA = 7
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10

# 单次检索最大条数
SEARCH_MAX_LIMIT = 10000

SORT_ASC = "asc"
SORT_DESC = "desc"

DEFAULT_SORT_LIST = [["dtEventTimeStamp", SORT_DESC], ["gseIndex", SORT_DESC], ["iterationIndex", SORT_DESC]]
DEFAULT_COLLECTOR_RT_KEY = "default_collector_rt_id"


class AccessTypeChoices(TextChoices):
    WEB = "0", gettext_lazy("WebUI")
    API = "1", gettext_lazy("API")
    CONSOLE = "2", gettext_lazy("Console")
    OTHER = "-1", gettext_lazy("Other")


class UserIdentifyTypeChoices(TextChoices):
    PERSONAL = "0", gettext_lazy("个人账号")
    PLATFORM = "1", gettext_lazy("平台账号")


class ResultCodeChoices(TextChoices):
    SUCCESS = "0", gettext_lazy("成功")
    FAILED = "-1", gettext_lazy("其他")


class CollectorSortFieldChoices(TextChoices):
    """
    日志采集器排序字段
    """

    DT_EVENT_TIME_STAMP = "dtEventTimeStamp", gettext_lazy("时间戳")
    GSE_INDEX = "gseIndex", gettext_lazy("GSE索引")
    ITERATION_INDEX = "iterationIndex", gettext_lazy("迭代索引")


# 默认日志采集器排序规则
DEFAULT_COLLECTOR_SORT_LIST = [
    {"order_field": CollectorSortFieldChoices.DT_EVENT_TIME_STAMP.value, "order_type": OrderTypeChoices.DESC.value},
    {"order_field": CollectorSortFieldChoices.GSE_INDEX.value, "order_type": OrderTypeChoices.DESC.value},
    {"order_field": CollectorSortFieldChoices.ITERATION_INDEX.value, "order_type": OrderTypeChoices.DESC.value},
]

OBJECT_FIELD_OPERATOR = [
    QueryConditionOperator.EQ,
    QueryConditionOperator.NEQ,
    QueryConditionOperator.GT,
    QueryConditionOperator.LT,
    QueryConditionOperator.GTE,
    QueryConditionOperator.LTE,
    QueryConditionOperator.INCLUDE,
    QueryConditionOperator.EXCLUDE,
    QueryConditionOperator.LIKE,
    QueryConditionOperator.NOT_LIKE,
    QueryConditionOperator.ISNULL,
    QueryConditionOperator.NOTNULL,
]

# 日志查询条件配置
COLLECT_SEARCH_CONFIG = CollectorSearchConfig(
    field_configs=[
        FieldSearchConfig(field=SYSTEM_ID, allow_operators=[QueryConditionOperator.INCLUDE, QueryConditionOperator.EQ]),
        FieldSearchConfig(field=ACTION_ID, allow_operators=[QueryConditionOperator.INCLUDE, QueryConditionOperator.EQ]),
        FieldSearchConfig(
            field=RESOURCE_TYPE_ID, allow_operators=[QueryConditionOperator.INCLUDE, QueryConditionOperator.EQ]
        ),
        FieldSearchConfig(
            field=ACCESS_TYPE, allow_operators=[QueryConditionOperator.INCLUDE, QueryConditionOperator.EQ]
        ),
        FieldSearchConfig(
            field=USER_IDENTIFY_TYPE, allow_operators=[QueryConditionOperator.INCLUDE, QueryConditionOperator.EQ]
        ),
        FieldSearchConfig(field=USERNAME, allow_operators=[QueryConditionOperator.INCLUDE, QueryConditionOperator.EQ]),
        FieldSearchConfig(field=EVENT_ID, allow_operators=[QueryConditionOperator.INCLUDE, QueryConditionOperator.EQ]),
        FieldSearchConfig(
            field=REQUEST_ID, allow_operators=[QueryConditionOperator.INCLUDE, QueryConditionOperator.EQ]
        ),
        FieldSearchConfig(
            field=INSTANCE_ID, allow_operators=[QueryConditionOperator.INCLUDE, QueryConditionOperator.EQ]
        ),
        FieldSearchConfig(
            field=ACCESS_SOURCE_IP, allow_operators=[QueryConditionOperator.INCLUDE, QueryConditionOperator.EQ]
        ),
        FieldSearchConfig(
            field=RESULT_CONTENT, allow_operators=[QueryConditionOperator.INCLUDE, QueryConditionOperator.EQ]
        ),
        FieldSearchConfig(
            field=LOG, allow_operators=[QueryConditionOperator.MATCH_ANY, QueryConditionOperator.MATCH_ALL]
        ),
        FieldSearchConfig(field=INSTANCE_DATA, allow_operators=OBJECT_FIELD_OPERATOR),
        FieldSearchConfig(field=INSTANCE_ORIGIN_DATA, allow_operators=OBJECT_FIELD_OPERATOR),
        FieldSearchConfig(field=EXTEND_DATA, allow_operators=OBJECT_FIELD_OPERATOR),
        FieldSearchConfig(field=SNAPSHOT_RESOURCE_TYPE_INFO, allow_operators=OBJECT_FIELD_OPERATOR),
        FieldSearchConfig(field=SNAPSHOT_ACTION_INFO, allow_operators=OBJECT_FIELD_OPERATOR),
        FieldSearchConfig(field=SNAPSHOT_INSTANCE_DATA, allow_operators=OBJECT_FIELD_OPERATOR),
        FieldSearchConfig(field=RESULT_CODE, allow_operators=[QueryConditionOperator.INCLUDE]),
        FieldSearchConfig(field=INSTANCE_NAME, allow_operators=[QueryConditionOperator.LIKE]),
        FieldSearchConfig(field=EVENT_CONTENT, allow_operators=[QueryConditionOperator.LIKE]),
        FieldSearchConfig(field=ACCESS_USER_AGENT, allow_operators=[QueryConditionOperator.LIKE]),
    ]
)

# 时间分区字段
DATE_FORMAT = "%Y%m%d"
DATE_PARTITION_FIELD = "thedate"
TIMESTAMP_PARTITION_FIELD = "dtEventTimeStamp"
