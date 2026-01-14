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
from typing import TypedDict

from django.utils.translation import gettext_lazy

from api.bk_log.constants import DEFAULT_RETENTION as _DEFAULT_RETENTION
from api.bk_log.constants import DEFAULT_STORAGE_REPLIES as _DEFAULT_STORAGE_REPLIES
from apps.meta.constants import (
    CollectorParamConditionMatchType as _CollectorParamConditionMatchType,
)
from apps.meta.constants import (
    CollectorParamConditionTypeEnum as _CollectorParamConditionTypeEnum,
)
from apps.meta.constants import ContainerCollectorType as _ContainerCollectorType
from apps.meta.constants import EtlConfigEnum as _EtlConfigEnum
from apps.meta.constants import LogReportStatus as _LogReportStatus
from apps.meta.constants import SystemStageEnum, SystemStatusEnum
from apps.meta.utils.fields import (
    FIELD_TYPE_DOUBLE,
    FIELD_TYPE_LONG,
    FIELD_TYPE_STRING,
    FIELD_TYPE_TEXT,
)
from core.choices import IntegerChoices, TextChoices
from services.web.databus.exceptions import FieldTypeNotMatchError

COLLECTOR_CONFIG_NAME_REGEX = r"^[\w\u4e00-\u9fa5]+$"
COLLECTOR_CONFIG_NAME_EN_REGEX = r"^[A-Za-z0-9_]+$"
COLLECTOR_NAME_MAX_LENGTH = 50

DEFAULT_LAST_TIME_TIMESTAMP = 0
DEFAULT_TARGET_OBJECT_TYPE = "HOST"
PLUGIN_CONDITION_SEPARATOR_OPTION = "="

DEFAULT_STORAGE_CONFIG_KEY = "default_cluster_id"
DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY = "default_replica_write_cluster_id"
EMPTY_CLUSTER_ID = -1
EMPTY_INDEX_SET_ID = 0
EMPTY_TABLE_ID = 0

CLEAN_CONFIG_JSON_CONF_KEY = "etl.clean_config.json_config.conf"

DEFAULT_ETL_PROCESSOR = "bkbase"
DEFAULT_COLLECTOR_SCENARIO = "row"
DEFAULT_CATEGORY_ID = "application_check"
DEFAULT_DATA_ENCODING = "UTF-8"

DEFAULT_TIME_FORMAT = "Unix Time Stamp(milliseconds)"
TRANSFER_TIME_FORMAT = "epoch_millis"
DEFAULT_TIME_ZONE = 0
DEFAULT_TIME_LEN = 13

COLLECTOR_PLUGIN_ID = "collector_plugin_id"

STORAGE_ALLOCATION_MIN_DAYS_KEY = "storage_allocation_min_days_{id}"

DEFAULT_RETENTION = _DEFAULT_RETENTION
DEFAULT_ALLOCATION_MIN_DAYS = 0
DEFAULT_STORAGE_REPLIES = _DEFAULT_STORAGE_REPLIES
DEFAULT_STORAGE_SHARDS = 1
DEFAULT_STORAGE_SHARD_SIZE = 10

INDEX_SET_CONFIG_KEY = "index_set_config"
REPLICA_WRITE_INDEX_SET_CONFIG_KEY = "replica_write_index_set_config"
REPLICA_WRITE_INDEX_SET_ID = "replica_write_index_set_id"

INDEX_SET_NAME_FORMAT = "BKAudit_{namespace}"
BKLOG_INDEX_SET_SCENARIO_ID = "log"

JOIN_DATA_PHYSICAL_RT_FORMAT = "bkaudit_join_data_{system_id}"
JOIN_DATA_RT_FORMAT = "bkaudit_{system_id}_{resource_type_id}"
JOIN_DATA_RUNNING_WAIT_TIME = 60
ASSET_RT_FORMAT = "asset_{system_id}_{resource_type_id}"

DEFAULT_REDIS_TAGS = ["Bk-Audit", "inland", "enable", "usr"]

RESOURCE_TYPE_DATA_RT_KEY = "bkaudit_resource_type_data"
RESOURCE_TYPE_DATA_CONFIG_KEY = "bkaudit_resource_type_config_data"
RESOURCE_TYPE_DATA_NAME_FORMAT = "bkaudit_resource_type_data{}"
ACTION_DATA_RT_KEY = "bkaudit_action_data"
ACTION_DATA_CONFIG_KEY = "bkaudit_action_config_data"
ACTION_DATA_NAME_FORMAT = "bkaudit_action_data_{}"
USER_INFO_DATA_RT_KEY = "bkaudit_user_info_data"
USER_INFO_DATA_CONFIG_KEY = "bkaudit_user_info_config_data"
USER_INFO_DATA_NAME_FORMAT = "bkaudit_user_info_data_{}"

API_PUSH_COLLECTOR_NAME_FORMAT = "{system_id}_{id}_{date}"
API_PUSH_ETL_RETRY_TIMES = 3
API_PUSH_ETL_RETRY_WAIT_TIME = 3

COLLECTOR_CHECK_TIME_PERIOD = 5  # 次
COLLECTOR_CHECK_TIME_RANGE = 60  # 秒
COLLECTOR_CHECK_AGG_SIZE = 10000
COLLECTOR_CHECK_PRECISION_THRESHOLD = 40000
COLLECTOR_CHECK_DECIMALS = 10
COLLECTOR_CHECK_EXTRA_CONFIG_KEY = "collector_check_extra_config"

BKBASE_API_MAX_PAGESIZE = 100

ContainerCollectorType = _ContainerCollectorType
EtlConfigEnum = _EtlConfigEnum
CollectorParamConditionTypeEnum = _CollectorParamConditionTypeEnum
CollectorParamConditionMatchType = _CollectorParamConditionMatchType

PULL_HANDLER_PRE_CHECK_TIMEOUT = int(os.getenv("BKAPP_PULL_HANDLER_PRE_CHECK_TIMEOUT", 5))  # ss

# Doris 事件存储配置
DORIS_EVENT_STORAGE_CONFIG_KEY = "doris_event_storage_config"
# Doris 事件结果表 ID
DORIS_EVENT_BKBASE_RT_ID_KEY = "doris_event_bkbase_rt_id"
# Doris 事件物理表
DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY = "doris_event_physical_table_name"

# Asset BKBase 结果表配置
ASSET_RISK_BKBASE_RT_ID_KEY = "asset_risk_bkbase_rt_id"
ASSET_STRATEGY_BKBASE_RT_ID_KEY = "asset_strategy_bkbase_rt_id"
ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY = "asset_strategy_tag_bkbase_rt_id"
ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY = "asset_ticket_permission_bkbase_rt_id"


class DefaultPullConfig:
    period = 1  # minute
    full_period = 60 * 24  # minute
    delay = 1  # minute
    limit = 1000  # count


class SensitivityChoice(TextChoices):
    PUBLIC = "public", gettext_lazy("公开")
    PRIVATE = "private", gettext_lazy("私有")
    CONFIDENTIAL = "confidential", gettext_lazy("机密")
    TOP_SECRET = "topsecret", gettext_lazy("绝密")


class EnvironmentChoice(TextChoices):
    CONTAINER = "container", gettext_lazy("容器")


class EtlProcessorChoice(TextChoices):
    BKBASE = "bkbase", gettext_lazy("计算平台")
    TRANSFER = "transfer", gettext_lazy("日志平台")


class CustomTypeEnum(TextChoices):
    LOG = "log", gettext_lazy("容器日志上报")
    OTLP_TRACE = "otlp_trace", gettext_lazy("otlpTrace上报")
    OTLP_LOG = "otlp_log", gettext_lazy("otlp日志上报")


class TargetNodeTypeChoices(TextChoices):
    SERVICE_TEMPLATE = "SERVICE_TEMPLATE", gettext_lazy("服务模板")
    SET_TEMPLATE = "SET_TEMPLATE", gettext_lazy("集群模版")
    TOPO = "TOPO", gettext_lazy("动态拓扑")
    INSTANCE = "INSTANCE", gettext_lazy("静态拓扑")


class RecordLogTypeChoices(TextChoices):
    SDK = "SDK", gettext_lazy("SDK接入")
    LOG = "LOG", gettext_lazy("LOG接入")


class SelectSdkTypeChoices(TextChoices):
    PYTHON_SDK = "PYTHON_SDK", gettext_lazy("Python SDK")
    JAVA_SDK = "JAVA_SDK", gettext_lazy("JAVA SDK")
    GO_SDK = "GO_SDK", gettext_lazy("Go SDK")


LogReportStatus = _LogReportStatus


class SnapshotReportStatus(TextChoices):
    NORMAL = "normal", gettext_lazy("正常")
    ABNORMAL = "abnormal", gettext_lazy("异常")
    UNSET = "unset", gettext_lazy("未配置")


class PluginSceneChoices(TextChoices):
    COLLECTOR = "collector", gettext_lazy("采集项")
    FLOW = "flow", gettext_lazy("数据开发")
    EVENT = "event", gettext_lazy("审计事件")


class SnapshotRunningStatus(TextChoices):
    CLOSED = "closed", gettext_lazy("已关闭")
    RUNNING = "running", gettext_lazy("运行中")
    FAILED = "failed", gettext_lazy("失败")
    PREPARING = "preparing", gettext_lazy("启动中")

    @classmethod
    def get_status(cls, value: bool):
        if value:
            return cls.PREPARING.value
        return cls.CLOSED.value


class SnapShotStorageChoices(TextChoices):
    HDFS = "hdfs", gettext_lazy("HDFS")
    REDIS = "redis", gettext_lazy("Redis")
    DORIS = "doris", gettext_lazy("Doris")


class SourcePlatformChoices(TextChoices):
    BKBASE = "bk_base", gettext_lazy("计算平台")
    BKLOG = "bk_log", gettext_lazy("日志平台")


class JsonSchemaFieldType(TextChoices):
    STRING = "string", gettext_lazy("String")
    NUMBER = "number", gettext_lazy("Number")
    INTEGER = "integer", gettext_lazy("Integer")
    OBJECT = "object", gettext_lazy("Object")
    ARRAY = "array", gettext_lazy("Array")
    BOOLEAN = "boolean", gettext_lazy("Boolean")
    NULL = "null", gettext_lazy("Null")
    ENUM = "enum", gettext_lazy("Enum")
    JSON = "json", gettext_lazy("Json")

    @classmethod
    def get_bkbase_field_type(cls, field_type: str) -> str:
        bkbase_field_map = {
            cls.STRING.value: FIELD_TYPE_STRING,
            cls.NUMBER.value: FIELD_TYPE_DOUBLE,
            cls.INTEGER.value: FIELD_TYPE_LONG,
            cls.OBJECT.value: FIELD_TYPE_TEXT,
            cls.ARRAY.value: FIELD_TYPE_TEXT,
            cls.BOOLEAN.value: FIELD_TYPE_STRING,
            cls.NULL.value: FIELD_TYPE_STRING,
            cls.ENUM.value: FIELD_TYPE_STRING,
            cls.JSON.value: FIELD_TYPE_TEXT,
        }
        try:
            return bkbase_field_map[field_type]
        except KeyError:
            raise FieldTypeNotMatchError()


class JoinDataPullType(TextChoices):
    PARTIAL = "partial", gettext_lazy("增量")
    FULL = "full", gettext_lazy("全量")


class JoinDataType(TextChoices):
    BASIC = "basic", gettext_lazy("通用关联数据")
    ASSET = "asset", gettext_lazy("资产")


class ClusterMode(TextChoices):
    MAIN = "main", gettext_lazy("主集群")
    REPLICA = "replica", gettext_lazy("双写集群")


class SnapshotStatusDict(TypedDict):
    """
    snapshot status map
    """

    status: SnapshotReportStatus


class TailLogStatusDict(TypedDict):
    """
    tail log map
    """

    system_id: str
    status: LogReportStatus
    status_msg: str
    last_time: str
    collector_count: int


class SystemStatusDict(TypedDict):
    """
    system status dict
    """

    system_status: SystemStatusEnum
    tail_log_item: TailLogStatusDict
    snapshot_status_item: SnapshotStatusDict
    has_permission_model: bool
    system_stage: SystemStageEnum
    system_status_msg: str


class SystemStatusDetailEnum(IntegerChoices):
    """
    系统状态详细枚举
    """

    # 未接入状态
    PENDING = 1, gettext_lazy("系统未接入审计中心")
    # 待完善状态
    NO_PERMISSION_MODEL = 2, gettext_lazy("系统待完善: 没有权限模型")
    NO_LOG_REPORT = 3, gettext_lazy("系统待完善: 没有日志上报")
    NO_ASSET_REPORT = 4, gettext_lazy("系统待完善: 没有配置资产上报")
    # 数据异常状态
    LOG_NO_DATA = 5, gettext_lazy("数据异常: 日志上报无数据")
    ASSET_ABNORMAL = 6, gettext_lazy("数据异常: 资产上报异常")
    # 正常状态
    NORMAL = 7, gettext_lazy("系统状态正常")

    def system_status(self) -> SystemStatusEnum:
        """
        获取系统状态
        """
        return {
            self.PENDING.value: SystemStatusEnum.PENDING,
            self.NO_PERMISSION_MODEL.value: SystemStatusEnum.INCOMPLETE,
            self.NO_LOG_REPORT.value: SystemStatusEnum.INCOMPLETE,
            self.NO_ASSET_REPORT.value: SystemStatusEnum.INCOMPLETE,
            self.LOG_NO_DATA.value: SystemStatusEnum.ABNORMAL,
            self.ASSET_ABNORMAL.value: SystemStatusEnum.ABNORMAL,
            self.NORMAL.value: SystemStatusEnum.NORMAL,
        }[self.value]
