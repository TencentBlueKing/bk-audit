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
from services.web.analyze.constants import FlowDataSourceNodeType

BKMONITOR_AGG_INTERVAL_MIN = 60  # s

HAS_UPDATE_TAG_ID = "-1"
HAS_UPDATE_TAG_NAME = gettext_lazy("Has Update")

# 本地更新字段，这些字段不会传递给后端策略，不会导致策略输出变化
LOCAL_UPDATE_FIELDS = ["strategy_name", "tags", "notice_groups"]


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

    @classmethod
    def get_config(cls, table_type: str) -> dict:
        """
        获取相关配置信息
        """

        match table_type:
            case cls.EVENT_LOG:
                return {"table_type": cls.EVENT_LOG, "source_type": FlowDataSourceNodeType.REALTIME}
            case cls.BUILD_ID_ASSET:
                return {"table_type": cls.BUILD_ID_ASSET, "source_type": FlowDataSourceNodeType.BATCH}
            # case cls.BIZ_ASSET:
            #     return {"table_type": cls.BIZ_ASSET, "source_type": FlowDataSourceNodeType.BATCH}
            case _:
                return {}


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


class FilterType(TextChoices):
    """
    筛选类型
    """

    NORMAL = "normal", gettext_lazy("常规")
    SQL = "sql", gettext_lazy("SQL")
