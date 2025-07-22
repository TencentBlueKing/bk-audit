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
from dataclasses import dataclass
from typing import List

from django.db.models import Q
from django.utils.translation import gettext_lazy

from apps.meta.models import Field
from apps.meta.utils.fields import FIELD_TYPE_LONG, FIELD_TYPE_STRING, FIELD_TYPE_TEXT
from core.choices import TextChoices
from services.web.databus.constants import DEFAULT_TIME_ZONE, TRANSFER_TIME_FORMAT

BKM_ALERT_SYNC_HOURS = int(os.getenv("BKAPP_BKM_ALERT_SYNC_HOURS", 3))
BKM_ALERT_BATCH_SIZE = 100

BKAUDIT_EVENT_RT_INDEX_NAME_FORMAT = "BkAudit_Event_{result_table}"
BKAUDIT_EVENT_RT_INDEX_SET_ID = "bkaudit_event_index_set_id"

BULK_ADD_EVENT_SIZE = 500

INDEX_TIME_FORMAT = "%Y%m%d"
WRITE_INDEX_FORMAT = "write_{date}_{table_id}"

EVENT_ES_CLUSTER_ID_KEY = "EVENT_ES_CLUSTER_ID"
EVENT_DORIS_CLUSTER_ID_KEY = "EVENT_DORIS_CLUSTER_ID"
EVENT_DATA_TIME_DURATION_HOURS = int(os.getenv("BKAPP_EVENT_DATA_TIME_DURATION_HOURS", 3))
EVENT_DATA_SORT_FIELD = "dtEventTimeStamp"
EVENT_TYPE_SPLIT_REGEX = os.getenv("BKAPP_EVENT_TYPE_SPLIT_REGEX", "[,;]")
EVENT_SYNC_START_TIME_KEY = "EVENT_SYNC_START_TIME"
EVENT_ESQUERY_DELAY_TIME = int(os.getenv("BKAPP_EVENT_ESQUERY_DELAY_TIME", str(10 * 60)))  # s

# 需要考虑数据传输的限制 <5MB 避免网关报错
RISK_SYNC_BATCH_SIZE = int(os.getenv("BKAPP_RISK_SYNC_BATCH_SIZE", 1000))
RISK_SYNC_SCROLL = os.getenv("BKAPP_RISK_SYNC_SCROLL", "5m")
RISK_SYNC_START_TIME_KEY = "RISK_SYNC_START_TIME"
RISK_ESQUERY_DELAY_TIME = int(os.getenv("BKAPP_RISK_ESQUERY_DELAY_TIME", str(10 * 60)))  # s
RISK_ESQUERY_SLICE_DURATION = int(os.getenv("BKAPP_RISK_ESQUERY_SLICE_DURATION", str(60 * 60)))  # s
RISK_EVENTS_SYNC_TIME = int(os.getenv("BKAPP_RISK_EVENTS_SYNC_TIME", "2"))  # day

SECURITY_PERSON_KEY = "SECURITY_PERSON"

RISK_OPERATE_NOTICE_CONFIG_KEY = "RISK_OPERATE_NOTICE_CONFIG"
DEFAULT_RISK_OPERATE_NOTICE_CONFIG = [{"msg_type": "mail"}]

# 风险列表有些字段长度过长来给它一个限制长度
LIST_RISK_FIELD_MAX_LENGTH = int(os.getenv("BKAPP_LIST_RISK_FIELD_MAX_LENGTH", 1024))

RISK_SHOW_FIELDS = [
    "risk_id",
    "event_content",
    "raw_event_id",
    "strategy_id",
    "event_evidence",
    "event_type",
    "event_data",
    "event_time",
    "event_source",
    "operator",
]


@dataclass
class TicketField:
    key: str
    name: str


class ApproveTicketFields:
    """
    审批单字段
    """

    TITLE = TicketField(key="title", name=gettext_lazy("标题"))
    RISK_ID = TicketField(key="risk_id", name=gettext_lazy("风险ID"))
    EVENT_CONTENT = TicketField(key="event_content", name=gettext_lazy("风险描述"))
    TAGS = TicketField(key="tags", name=gettext_lazy("标签"))
    OPERATOR = TicketField(key="operator", name=gettext_lazy("责任人"))
    RISK_LEVEL = TicketField(key="risk_level", name=gettext_lazy("风险等级"))
    PROCESS_APPLICATION_NAME_FIELD = TicketField(key="process_application_name", name=gettext_lazy("处理套餐名称"))
    DESCRIPTION = TicketField(key="description", name=gettext_lazy("说明"))
    RISK_URL = TicketField(key="risk_url", name=gettext_lazy("审计关联单据"))


class EventSourceTypeChoices(TextChoices):
    """
    事件来源类型
    """

    BKM = "bkm", gettext_lazy("BK Monitor")
    AIOPS = "aiops", gettext_lazy("BK Base AIOps")
    API = "api", gettext_lazy("API")


class EventMappingFields:
    """
    审计事件标准字段
    """

    @property
    def fields(self):
        return [
            self.EVENT_ID,
            self.EVENT_CONTENT,
            self.RAW_EVENT_ID,
            self.STRATEGY_ID,
            self.EVENT_EVIDENCE,
            self.EVENT_TYPE,
            self.EVENT_DATA,
            self.EVENT_TIME,
            self.EVENT_SOURCE,
            self.OPERATOR,
        ]

    EVENT_ID = Field(
        field_name="event_id",
        alias_name="event_id",
        description=gettext_lazy("事件ID"),
        field_type=FIELD_TYPE_STRING,
        option=dict(),
    )

    EVENT_CONTENT = Field(
        field_name="event_content",
        alias_name="event_content",
        description=gettext_lazy("事件描述"),
        field_type=FIELD_TYPE_TEXT,
        is_analyzed=True,
        is_text=True,
        option=dict(),
        is_required=False,
    )

    RAW_EVENT_ID = Field(
        field_name="raw_event_id",
        alias_name="raw_event_id",
        description=gettext_lazy("原始事件ID"),
        field_type=FIELD_TYPE_STRING,
        option=dict(),
    )

    STRATEGY_ID = Field(
        field_name="strategy_id",
        alias_name="strategy_id",
        description=gettext_lazy("命中策略(ID)"),
        field_type=FIELD_TYPE_LONG,
        option=dict(),
    )

    EVENT_EVIDENCE = Field(
        field_name="event_evidence",
        alias_name="event_evidence",
        description=gettext_lazy("事件证据"),
        field_type=FIELD_TYPE_TEXT,
        is_required=False,
        is_analyzed=True,
        is_text=True,
        option=dict(),
    )

    EVENT_TYPE = Field(
        field_name="event_type",
        alias_name="event_type",
        description=gettext_lazy("事件类型"),
        field_type=FIELD_TYPE_TEXT,
        is_required=False,
        is_analyzed=True,
        is_text=True,
        option=dict(),
    )

    EVENT_DATA = Field(
        field_name="event_data",
        alias_name="event_data",
        description=gettext_lazy("事件拓展数据"),
        field_type=FIELD_TYPE_TEXT,
        option={},
        is_analyzed=True,
        is_required=False,
        is_text=True,
    )

    EVENT_TIME = Field(
        field_name="event_time",
        alias_name="event_time",
        description=gettext_lazy("事件发生时间"),
        field_type=FIELD_TYPE_LONG,
        option={"time_zone": DEFAULT_TIME_ZONE, "time_format": TRANSFER_TIME_FORMAT},
        is_time=True,
    )

    EVENT_SOURCE = Field(
        field_name="event_source",
        alias_name="event_source",
        description=gettext_lazy("事件来源"),
        field_type=FIELD_TYPE_STRING,
        option=dict(),
    )

    OPERATOR = Field(
        field_name="operator",
        alias_name="operator",
        description=gettext_lazy("负责人"),
        field_type=FIELD_TYPE_TEXT,
        is_text=True,
        is_analyzed=True,
        option=dict(),
    )


class RiskStatus(TextChoices):
    """
    所有风险状态

    ```mermaid
    graph TB
    A(风险单产生)
    B(自动处理审批中)
    C("套餐处理中(自动)")
    D(已关单)
    E(待处理)
    F("套餐处理中(人工发起)")
    A --配置了处理规则--> B
    A --未配置处理规则--> E
    B --审批通过--> C
    B --审批不通过--> E
    C --成功--> D
    C --失败-->E
    E --手动关单--> D
    E --转单--> E
    E --处理套餐--> F
    F --配置了成功就关闭单据--> D
    F --配置了成功也需要人工处理--> E
    ```
    """

    # 新
    NEW = "new", gettext_lazy("新")

    # 人工处理
    AWAIT_PROCESS = "await_deal", gettext_lazy("待处理")
    FOR_APPROVE = "for_approve", gettext_lazy("自动处理审批中")

    # 处理套餐
    AUTO_PROCESS = "auto_process", gettext_lazy("套餐处理中")

    # 关闭
    CLOSED = "closed", gettext_lazy("已关单")


class TicketNodeStatus(TextChoices):
    """
    单据节点状态
    """

    RUNNING = "running", gettext_lazy("运行中")
    FINISHED = "finished", gettext_lazy("已完成")


class RiskRuleOperator(TextChoices):
    """
    风险规则匹配符
    """

    EQUAL = "=", gettext_lazy("=")
    NOT_EQUAL = "!=", gettext_lazy("!=")
    GREATER_THAN = ">", gettext_lazy(">")
    GREATER_THAN_EQUAL = ">=", gettext_lazy(">=")
    LESS_THAN = "<", gettext_lazy("<")
    LESS_THAN_EQUAL = "<=", gettext_lazy("<=")

    @classmethod
    def build_query_filter(cls, scope: List[dict]) -> Q:
        """
        {
            "scope": [
                {
                    "field": "operator",
                    "operator": "=",
                    "value": [
                        "admin"
                    ],
                    "connector": "AND",
                }
            ]
        }
        """

        q = Q()
        for _scope in scope:
            exclude, filter_format = False, "{}"
            field, operator, value, connector = (
                _scope["field"],
                _scope["operator"],
                _scope["value"],
                _scope.get("connector", "AND"),
            )
            match operator:
                case cls.EQUAL:
                    if field in [EventMappingFields.OPERATOR.field_name, EventMappingFields.EVENT_TYPE.field_name]:
                        exclude, filter_format = False, "{}__contains"
                    else:
                        exclude, filter_format = False, "{}"
                case cls.NOT_EQUAL:
                    if field in [EventMappingFields.OPERATOR.field_name, EventMappingFields.EVENT_TYPE.field_name]:
                        exclude, filter_format = True, "{}__contains"
                    else:
                        exclude, filter_format = True, "{}"
                case cls.GREATER_THAN:
                    exclude, filter_format = False, "{}__gt"
                case cls.GREATER_THAN_EQUAL:
                    exclude, filter_format = False, "{}__gte"
                case cls.LESS_THAN:
                    exclude, filter_format = False, "{}__lt"
                case cls.LESS_THAN_EQUAL:
                    exclude, filter_format = False, "{}__lte"
            _q = Q()
            filter_field = filter_format.format(field)
            for v in value:
                _q |= ~Q(**{filter_field: v}) if exclude else Q(**{filter_field: v})
            if connector.lower() == "and":
                q &= _q
            else:
                q |= _q
        return q


class RiskLabel(TextChoices):
    NORMAL = "normal", gettext_lazy("正常")
    MISREPORT = "misreport", gettext_lazy("误报")


class RiskViewType(TextChoices):
    """
    风险视图类型
    """

    ALL = "all", gettext_lazy("全部")
    TODO = "todo", gettext_lazy("待处理")
    WATCH = "watch", gettext_lazy("待关注")


class RiskFields:
    """
    工单字段
    """

    @property
    def fields(self) -> List[Field]:
        return [
            self.RISK_ID,
            self.RISK_CONTENT,
            self.STRATEGY_ID,
            self.RAW_EVENT_ID,
            self.RISK_OPERATOR,
            self.RISK_EVIDENCE,
        ]

    RISK_ID = Field(field_name="risk_id", alias_name=gettext_lazy("风险ID"))
    RISK_CONTENT = Field(field_name="risk_content", alias_name=gettext_lazy("风险描述"))
    STRATEGY_ID = Field(field_name="strategy_id", alias_name=gettext_lazy("策略ID"))
    RAW_EVENT_ID = Field(field_name="raw_event_id", alias_name=gettext_lazy("原始事件ID"))
    RISK_OPERATOR = Field(field_name="risk_operator", alias_name=gettext_lazy("风险责任人"))
    RISK_EVIDENCE = Field(field_name="risk_evidence", alias_name=gettext_lazy("风险证据"))
    RISK_DATA = Field(field_name="risk_data", alias_name=gettext_lazy("拓展数据"))


# 事件基础字段中需要映射的字段
EVENT_BASIC_MAP_FIELDS = [
    EventMappingFields.RAW_EVENT_ID,
    EventMappingFields.EVENT_SOURCE,
    EventMappingFields.OPERATOR,
]

# ES 搜索原始字段,其值不做处理
ES_SEARCH_ORIGIN_FIELDS = [
    EventMappingFields.RAW_EVENT_ID.field_name,
]
