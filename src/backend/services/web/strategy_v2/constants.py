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
from typing import TypedDict

from django.utils.translation import gettext_lazy

from core.choices import TextChoices
from services.web.risk.constants import RISK_EVENTS_SYNC_TIME

BKMONITOR_AGG_INTERVAL_MIN = 60  # s

HAS_UPDATE_TAG_ID = "-1"
HAS_UPDATE_TAG_NAME = gettext_lazy("Upgradable")

# 未标签
NO_TAG_ID = "-2"
NO_TAG_NAME = gettext_lazy("No Tag")

# 本地更新字段，这些字段不会传递给后端策略，不会导致策略输出变化
LOCAL_UPDATE_FIELDS = [
    "strategy_name",
    "tags",
    "notice_groups",
    "description",
    "risk_level",
    "risk_hazard",
    "risk_guidance",
    "risk_title",
    "processor_groups",
]

# 策略可用的调度时间依赖于事件的查询周期
STRATEGY_SCHEDULE_TIME = max(1, RISK_EVENTS_SYNC_TIME - 1)  # day


class StrategyStatusChoices(TextChoices):
    """
    Strategy Status
    """

    # 停用
    DISABLED = "disabled", gettext_lazy("Disabled")

    # 失败
    FAILED = "failed", gettext_lazy("Failed")
    START_FAILED = "start_failed", gettext_lazy("Start Failed")
    UPDATE_FAILED = "update_failed", gettext_lazy("Update Failed")
    STOP_FAILED = "stop_failed", gettext_lazy("Stop Failed")
    DELETE_FAILED = "delete_failed", gettext_lazy("Delete Failed")

    # 处理中
    STARTING = "starting", gettext_lazy("Starting")
    UPDATING = "updating", gettext_lazy("Updating")
    STOPPING = "stopping", gettext_lazy("Stopping")

    # 正常
    RUNNING = "running", gettext_lazy("Running")


class StrategyOperator(TextChoices):
    """策略匹配符"""

    EQ = "eq", gettext_lazy("Equal")
    NEQ = "neq", gettext_lazy("NotEqual")
    REG = "reg", gettext_lazy("Regex")
    NREG = "nreg", gettext_lazy("NotRegex")
    INCLUDE = "include", gettext_lazy("Include")
    EXCLUDE = "exclude", gettext_lazy("Exclude")


class ConnectorChoices(TextChoices):
    """连接器"""

    AND = "and", gettext_lazy("AND")
    OR = "or", gettext_lazy("OR")


class StrategyAlgorithmOperator(TextChoices):
    """检测算法匹配符"""

    EQ = "eq", "="
    NEQ = "neq", "!="
    GT = "gt", ">"
    GTE = "gte", ">="
    LT = "lt", "<"
    LTE = "lte", "<="


class StrategyAlertLevel(TextChoices):
    """告警类型"""

    FATAL = "1", gettext_lazy("致命")
    WARNING = "2", gettext_lazy("预警")
    REMIND = "3", gettext_lazy("提醒")

    @classmethod
    def default_level(cls):
        return cls.WARNING.value


class TableType(TextChoices):
    """结果表类型"""

    EVENT_LOG = "EventLog", gettext_lazy("Event Log")
    BUILD_ID_ASSET = "BuildIn", gettext_lazy("Asset Data")
    BIZ_RT = "BizRt", gettext_lazy("Biz RT")


class BKBaseProcessingType(TextChoices):
    """
    计算类型
    """

    CDC = "cdc_static", gettext_lazy("CDC")


class ResultTableType(TextChoices):
    """
    结果表类型
    """

    STATIC = "upsert_static", gettext_lazy("Static")


class MappingType(TextChoices):
    """
    映射字段类型
    """

    PUBLIC = "public", gettext_lazy("Public Field")
    ACTION = "action", gettext_lazy("Extend Field")


class RiskLevel(TextChoices):
    """
    风险等级
    """

    HIGH = "HIGH", gettext_lazy("高")
    MIDDLE = "MIDDLE", gettext_lazy("中")
    LOW = "LOW", gettext_lazy("低")


class EventInfoField(TypedDict):
    """
    事件信息字段
    """

    field_name: str
    display_name: str
    description: str
    example: str


class StrategyType(TextChoices):
    """
    策略类型
    """

    RULE = "rule", gettext_lazy("规则策略")
    MODEL = "model", gettext_lazy("模型策略")


class LinkTableJoinType(TextChoices):
    """
    联表连接类型
    """

    INNER_JOIN = "inner_join", gettext_lazy("内连接")
    LEFT_JOIN = "left_join", gettext_lazy("左连接")
    RIGHT_JOIN = "right_join", gettext_lazy("右连接")
    FULL_OUTER_JOIN = "full_outer_join", gettext_lazy("全连接")


class LinkTableTableType(TextChoices):
    """
    联表表类型
    """

    EVENT_LOG = TableType.EVENT_LOG
    BUILD_ID_ASSET = TableType.BUILD_ID_ASSET
    BIZ_RT = TableType.BIZ_RT


class ListLinkTableSortField(TextChoices):
    """
    联表排序字段
    """

    NAME = "name", gettext_lazy("Link Table Name")
    UPDATED_AT = "updated_at", gettext_lazy("Updated At")
    UPDATED_BY = "updated_by", gettext_lazy("Updated By")


class BkBaseStorageType(TextChoices):
    """
    BKBase 存储类型
    """

    HDFS = "hdfs", gettext_lazy("HDFS")
    REDIS = "redis", gettext_lazy("Redis")
    KAFKA = "kafka", gettext_lazy("Kafka")


# 业务下的RT表允许的存储类型
BIZ_RT_TABLE_ALLOW_STORAGES = {
    BkBaseStorageType.HDFS.value,
}
