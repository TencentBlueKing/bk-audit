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

from core.choices import TextChoices, register_choices
from core.sql.constants import (
    AggregateType,
    FieldType,
    FilterConnector,
    JoinType,
    Operator,
)
from services.web.analyze.constants import FlowDataSourceNodeType
from services.web.risk.constants import RISK_EVENTS_SYNC_TIME

BKMONITOR_AGG_INTERVAL_MIN = 60  # s

HAS_UPDATE_TAG_ID = "-1"
HAS_UPDATE_TAG_NAME = gettext_lazy("Upgradable")

# 远程更新字段（白名单），这些字段变化会传递给后端策略，会导致策略输出变化
# 只有在此列表中的字段变更时，才会触发远程 Flow 更新
REMOTE_UPDATE_FIELDS = [
    "control_id",
    "control_version",
    "sql",
    "configs",
    "link_table_uid",
    "link_table_version",
    "strategy_type",
]

# 事件基本配置字段
EVENT_BASIC_CONFIG_FIELD = "event_basic_field_configs"

# 事件基本配置排序字段
EVENT_BASIC_CONFIG_SORT_FIELD = "field_name"

# 事件基本配置字段和远程服务相关字段，这些字段变更会导致策略输出变化
EVENT_BASIC_CONFIG_REMOTE_FIELDS = ["map_config"]

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


class ListTableType(TextChoices):
    """可获取结果表类型"""

    EVENT_LOG = "EventLog", gettext_lazy("Event Log")
    BUILD_ID_ASSET = "BuildIn", gettext_lazy("Asset Data")
    BIZ_RT = "BizRt", gettext_lazy("Other Data")


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
    is_show: bool
    duplicate_field: bool


class StrategyType(TextChoices):
    """
    策略类型
    """

    RULE = "rule", gettext_lazy("规则策略")
    MODEL = "model", gettext_lazy("模型策略")


class StrategySource(TextChoices):
    USER = "user", gettext_lazy("用户创建")
    SYSTEM = "system", gettext_lazy("系统创建")


class LinkTableTableType(TextChoices):
    """
    联表表类型
    """

    EVENT_LOG = "EventLog", gettext_lazy("Event Log")
    BUILD_ID_ASSET = "BuildIn", gettext_lazy("Asset Data")
    BIZ_RT = "BizRt", gettext_lazy("Other Data")


class ListLinkTableSortField(TextChoices):
    """
    联表排序字段
    """

    NAME = "name", gettext_lazy("Link Table Name")
    UPDATED_AT = "updated_at", gettext_lazy("Updated At")
    UPDATED_BY = "updated_by", gettext_lazy("Updated By")
    CREATED_AT = "created_at", gettext_lazy("Created At")
    CREATED_BY = "created_by", gettext_lazy("Created By")


class BkBaseStorageType(TextChoices):
    """
    BKBase 存储类型
    """

    HDFS = "hdfs", gettext_lazy("HDFS")
    REDIS = "redis", gettext_lazy("Redis")
    KAFKA = "kafka", gettext_lazy("Kafka")
    DORIS = "doris", gettext_lazy("Doris")
    PULSAR = "pulsar", gettext_lazy("Pulsar")


# 可用于实时计算的存储类型
ALLOWED_REALTIME_STORAGES = {
    BkBaseStorageType.KAFKA.value,
    BkBaseStorageType.PULSAR.value,
}

# 可用于离线计算的存储类型
ALLOWED_OFFLINE_STORAGES = {
    BkBaseStorageType.HDFS.value,
}

# 业务下的RT表允许的存储类型
BIZ_RT_TABLE_ALLOW_STORAGES = {
    BkBaseStorageType.HDFS.value,
    BkBaseStorageType.KAFKA.value,
    BkBaseStorageType.PULSAR.value,
}


class RuleAuditConfigType(TextChoices):
    """
    规则审计配置类型
    """

    EVENT_LOG = TableType.EVENT_LOG.value, TableType.EVENT_LOG.label
    BUILD_ID_ASSET = TableType.BUILD_ID_ASSET.value, TableType.BUILD_ID_ASSET.label
    BIZ_RT = "BizRt", gettext_lazy("Other Data")
    LINK_TABLE = "LinkTable", gettext_lazy("Link Table Data")


class RuleAuditSourceType(TextChoices):
    """
    规则审计调度类型
    """

    REALTIME = FlowDataSourceNodeType.REALTIME.value, FlowDataSourceNodeType.REALTIME.label
    BATCH = FlowDataSourceNodeType.BATCH.value, FlowDataSourceNodeType.BATCH.label


# BKBASE 内置字段
BKBASE_INTERNAL_FIELD = ["timestamp", "dtEventTime", "localTime", "_startTime_", "_endTime_"]

# 联表连接类型
LinkTableJoinType = JoinType
# 规则审计聚合类型
RuleAuditAggregateType = AggregateType
# 规则审计字段类型
RuleAuditFieldType = FieldType


# 规则审计条件操作符
class RuleAuditConditionOperator(TextChoices):
    """
    规则审计条件操作符
    """

    EQ = Operator.EQ.value, Operator.EQ.label
    NEQ = Operator.NEQ.value, Operator.NEQ.label
    GT = Operator.GT.value, Operator.GT.label
    LT = Operator.LT.value, Operator.LT.label
    GTE = Operator.GTE.value, Operator.GTE.label
    LTE = Operator.LTE.value, Operator.LTE.label
    INCLUDE = Operator.INCLUDE.value, Operator.INCLUDE.label
    EXCLUDE = Operator.EXCLUDE.value, Operator.EXCLUDE.label
    LIKE = Operator.LIKE.value, Operator.LIKE.label
    NOT_LIKE = Operator.NOT_LIKE.value, Operator.NOT_LIKE.label
    ISNULL = Operator.ISNULL.value, Operator.ISNULL.label
    NOTNULL = Operator.NOTNULL.value, Operator.NOTNULL.label


# 规则审计条件连接符
RuleAuditWhereConnector = FilterConnector

# 策略运行状态默认时间间隔(天)
STRATEGY_STATUS_DEFAULT_INTERVAL = 30 * 6

# 策略关联风险默认时间间隔(天)
STRATEGY_RISK_DEFAULT_INTERVAL = 30 * 6


@register_choices("strategy_field_source")
class StrategyFieldSourceEnum(TextChoices):
    """
    策略字段来源
    """

    BASIC = "basic", gettext_lazy("基本字段")
    DATA = "data", gettext_lazy("数据字段")
    EVIDENCE = "evidence", gettext_lazy("证据字段")
    RISK_META = "risk_meta", gettext_lazy("风险元字段")
