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

CHECK_FLOW_STATUS_SLEEP_SECONDS = 5

BKBASE_ATTR_GROUP_FIELD_NAME = "attr_group"
BKBASE_GROUP_BY_FIELD_CONTAINER_TYPE = "group"
BKBASE_SYSTEM_FIELD_ROLE = "system"
BKBASE_FLOW_CONSUMING_MODE = "continue"
BKBASE_PLAN_TAG = "BkAudit"
BKBASE_PLAN_PUBLISHED_STATUS = "published"
BKBASE_DEFAULT_OFFSET = 0
BKBASE_DEFAULT_START_OFFSET = 0
BKBASE_DEFAULT_END_OFFSET = 1
BKBASE_DEFAULT_WINDOW_SIZE = 1
BKBASE_DEFAULT_WINDOW_COLOR = "#58c5db"
BKBASE_DEFAULT_BASELINE_LOCATION = "start"
BKBASE_DEFAULT_COUNT_FREQ = 1
BKBASE_ERROR_LOG_LEVEL = "ERROR"
BKBASE_ORIGIN_DATA_FIELD = "origin_data"
BKBASE_STRATEGY_ID_FIELD = "strategy_id"


class ControlTypeChoices(TextChoices):
    """Control Type"""

    BKM = "BKM", gettext_lazy("Operate Audit")
    AIOPS = "AIOps", gettext_lazy("BK Base AIOps")


class FlowStatusChoices(TextChoices):
    """Flow Status"""

    SUCCESS = "success", gettext_lazy("成功")
    FAILURE = "failure", gettext_lazy("失败")
    OTHER = "other", gettext_lazy("其他")


class FlowDataSourceNodeType(TextChoices):
    """Flow Data Source Node"""

    REALTIME = "stream_source", gettext_lazy("RealTime")
    BATCH = "batch_join_source", gettext_lazy("Batch Join")
    BATCH_REAL = "batch_source", gettext_lazy("Batch")


class ResultTableType(TextChoices):
    CDC = "cdc_static", gettext_lazy("CDC")
    STATIC = "upsert_static", gettext_lazy("Static Table")


class FlowSQLNodeType(TextChoices):
    """Flow SQL Node"""

    REALTIME = "realtime", gettext_lazy("RealTime")
    BATCH_V2 = "batchv2", gettext_lazy("BatchV2")

    @classmethod
    def get_sql_node_type(cls, node_type: str) -> str:
        if node_type == FlowDataSourceNodeType.REALTIME.value:
            return cls.REALTIME.value
        elif node_type == FlowDataSourceNodeType.BATCH.value:
            return cls.BATCH_V2.value
        else:
            raise KeyError("NodeType [%s] Not Exists" % node_type)


class ScenePlanServingMode(TextChoices):
    """
    Serving Mode
    """

    REALTIME = "realtime", gettext_lazy("RealTime")
    BATCH = "offline", gettext_lazy("Batch")


class FlowStatusToggleChoices(TextChoices):
    """Flow Status"""

    START = "start", gettext_lazy("Start Flow")
    STOP = "stop", gettext_lazy("Stop Flow")
    RESTART = "restart", gettext_lazy("Restart Flow")


class FlowNodeStatusChoices(TextChoices):
    """Flow Node Choices"""

    RUNNING = "running", gettext_lazy("Running")
    NO_START = "no-start", gettext_lazy("Not Start")
    FAILED = "failure", gettext_lazy("Failed")


class FilterOperator(TextChoices):
    """
    Filter Operator
    """

    EQUAL = "=", gettext_lazy("=")
    NOT_EQUAL = "!=", gettext_lazy("!=")
    GRATER_THAN = ">", gettext_lazy(">")
    LESS_THAN = "<", gettext_lazy("<")
    GRATER_THAN_EQUAL = ">=", gettext_lazy(">=")
    LESS_THAN_EQUAL = "<=", gettext_lazy("<=")


class FilterConnector(TextChoices):
    """
    Filter Connector
    """

    AND = "and", gettext_lazy("AND")
    OR = "or", gettext_lazy("OR")


class WindowDependencyRule(TextChoices):
    """
    Dependency Rule
    """

    NO_FAILED = "no_failed", gettext_lazy("No Failed")
    ALL_FINISHED = "all_finished", gettext_lazy("All Finished")
    AT_LEAST_ONE = "at_least_one_finished", gettext_lazy("At Least One Finished")


class OutputBaselineType(TextChoices):
    """
    Output Baseline Type
    """

    UPSTREAM = "upstream_result_table", gettext_lazy("Upstream")
    SCHEDULE = "schedule_time", gettext_lazy("Schedule")


class OffsetUnit(TextChoices):
    """
    Offset Unit
    """

    HOUR = "hour", gettext_lazy("Hour")
    DAY = "day", gettext_lazy("Day")
    WEEK = "week", gettext_lazy("Week")
    MONTH = "month", gettext_lazy("Month")


class WindowType(TextChoices):
    """
    Window Type
    """

    SCROLL = "scroll", gettext_lazy("Scroll")
    SLIDE = "slide", gettext_lazy("Slide")
    WHOLE = "whole", gettext_lazy("Whole")
