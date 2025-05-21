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
from functools import cached_property
from typing import List, Optional

from django.utils.translation import gettext_lazy
from pydantic import BaseModel

from apps.meta.models import Field
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
from core.choices import TextChoices, register_choices
from core.constants import OrderTypeChoices
from core.sql.constants import FieldType
from core.sql.model import BaseField
from services.web.query.utils.field import (
    LOG_SEARCH_ALL_FIELDS,
    LOG_SEARCH_SNAPSHOT_FIELDS,
    LOG_SEARCH_SNAPSHOT_FIELDS_MAP,
    LOG_SEARCH_STANDARD_FIELDS,
    LOG_SEARCH_STANDARD_FIELDS_MAP,
    LOG_SEARCH_SYSTEM_FIELDS_MAP,
)
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

# 日志导出字段Keys长度限制
LOG_EXPORT_FIELD_KEYS_MAX_LENGTH = 512


class LogExportField(BaseField):
    """
    日志导出字段
    """

    raw_name: str
    display_name: str = ""

    # 非必须
    table: str = ""
    field_type: Optional[FieldType] = None  # 字段类型

    @cached_property
    def full_key(self) -> str:
        """
        获取字段的完整键名
        """

        return LOG_FIELD_KEY_JOIN_CHAR.join([self.raw_name, *self.keys])


class FileExportResult(BaseModel):
    """
    文件导出结果
    """

    origin_name: str  # 原始文件名
    storage_name: str  # 存储文件名
    size: int  # 文件大小(单位:字节)
    url: str  # 下载地址


@register_choices("log_export_task")
class TaskEnum(TextChoices):
    """
    日志导出任务状态
    """

    READY = "READY", gettext_lazy("就绪")
    RUNNING = "RUNNING", gettext_lazy("执行中")
    SUCCESS = "SUCCESS", gettext_lazy("成功")
    FAILURE = "FAILURE", gettext_lazy("失败")
    EXPIRED = "EXPIRED", gettext_lazy("已过期")

    @classmethod
    def get_schedule_status(cls) -> List["TaskEnum"]:
        """
        获取可调度的状态
        """

        return [
            cls.READY,
            cls.FAILURE,
        ]


class LogExportFieldScope(TextChoices):
    """
    日志导出字段范围
    """

    ALL = "all", gettext_lazy("全部字段")
    STANDARD = "standard", gettext_lazy("标准字段")
    SNAPSHOT = "snapshot", gettext_lazy("快照字段")
    SPECIFIED = "specified", gettext_lazy("指定字段")

    @classmethod
    def get_fields(cls, scope: str) -> List[Field]:
        """
        获取字段范围对应的字段
        """

        return {
            cls.ALL.value: LOG_SEARCH_ALL_FIELDS,
            cls.STANDARD.value: LOG_SEARCH_STANDARD_FIELDS,
            cls.SNAPSHOT.value: LOG_SEARCH_SNAPSHOT_FIELDS,
            cls.SPECIFIED.value: [],
        }.get(scope)


# 日志字段 key 拼接字符
LOG_FIELD_KEY_JOIN_CHAR = ","

# 日志导出根目录
LOG_EXPORT_ROOT_PATH = "log_export"
# 文件上传路径
LOG_EXPORT_FILE_NAME_FORMAT = LOG_EXPORT_ROOT_PATH + "/{namespace}/{file_name}"


@register_choices("query_field_category")
class FieldCategoryEnum(TextChoices):
    """
    字段分类
    """

    STANDARD = "standard", gettext_lazy("标准字段")
    SNAPSHOT = "snapshot", gettext_lazy("快照字段")
    SYSTEM = "system", gettext_lazy("系统字段")
    CUSTOM = "custom", gettext_lazy("自定义字段")

    @property
    def color(self) -> str:
        """
        返回颜色
        """

        return {
            self.STANDARD.value: '#C6EFCE',
            self.SNAPSHOT.value: '#FCE4D6',
            self.SYSTEM.value: '#DDEBF7',
            self.CUSTOM.value: '#4F81BD',
        }.get(self.value, '#FFFFFF')

    @classmethod
    def get_category_by_field(cls, field: LogExportField) -> "FieldCategoryEnum":
        """
        获取字段分类
        """

        for k, v in [
            (LOG_SEARCH_STANDARD_FIELDS_MAP, cls.STANDARD),
            (LOG_SEARCH_SNAPSHOT_FIELDS_MAP, cls.SNAPSHOT),
            (LOG_SEARCH_SYSTEM_FIELDS_MAP, cls.SYSTEM),
        ]:
            if field.full_key in k:
                return v
        return cls.CUSTOM

    @classmethod
    def get_orders(cls) -> List["FieldCategoryEnum"]:
        """
        获取排序顺序
        """

        return [
            cls.CUSTOM,
            cls.STANDARD,
            cls.SNAPSHOT,
            cls.SYSTEM,
        ]
