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
from apps.meta.utils.fields import (
    FIELD_TYPE_LONG,
    FIELD_TYPE_OBJECT,
    FIELD_TYPE_STRING,
    FIELD_TYPE_TEXT,
)
from core.choices import TextChoices, register_choices
from core.exporter.constants import ExportField
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


# 原始事件ID 备注
RAW_EVENT_ID_REMARK = gettext_lazy("系统会将原始事件ID相同的事件，关联至同一个未关闭的风险单据")


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

    @classmethod
    def dynamic_json_fields(cls):
        """
        动态JSON字段
        """

        return [cls.EVENT_DATA, cls.EVENT_EVIDENCE]

    EVENT_ID = Field(
        field_name="event_id",
        alias_name="event_id",
        description=gettext_lazy("事件ID"),
        field_type=FIELD_TYPE_STRING,
        option=dict(),
        is_index=True,
        is_dimension=False,
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
        is_dimension=False,
    )

    RAW_EVENT_ID = Field(
        field_name="raw_event_id",
        alias_name="raw_event_id",
        description=gettext_lazy("原始事件ID"),
        field_type=FIELD_TYPE_STRING,
        option=dict(),
        is_index=True,
        is_dimension=False,
        property={
            "remark": RAW_EVENT_ID_REMARK,
        },
    )

    STRATEGY_ID = Field(
        field_name="strategy_id",
        alias_name="strategy_id",
        description=gettext_lazy("命中策略(ID)"),
        field_type=FIELD_TYPE_LONG,
        option=dict(),
        is_index=True,
        is_dimension=False,
    )

    EVENT_EVIDENCE = Field(
        field_name="event_evidence",
        alias_name="event_evidence",
        description=gettext_lazy("事件证据"),
        field_type=FIELD_TYPE_OBJECT,
        is_required=False,
        is_analyzed=True,
        is_text=True,
        option={"meta_field_type": FIELD_TYPE_TEXT},  # ES 日志的字段类型为 text
        is_json=True,
        is_dimension=False,
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
        is_dimension=False,
    )

    EVENT_DATA = Field(
        field_name="event_data",
        alias_name="event_data",
        description=gettext_lazy("事件拓展数据"),
        field_type=FIELD_TYPE_OBJECT,
        option={"meta_field_type": FIELD_TYPE_TEXT},  # ES 日志的字段类型为 text
        is_analyzed=True,
        is_required=False,
        is_text=True,
        is_json=True,
        is_dimension=False,
    )

    EVENT_TIME = Field(
        field_name="event_time",
        alias_name="event_time",
        description=gettext_lazy("事件发生时间"),
        field_type=FIELD_TYPE_LONG,
        option={"time_zone": DEFAULT_TIME_ZONE, "time_format": TRANSFER_TIME_FORMAT},
        is_time=True,
        is_dimension=False,
    )

    EVENT_SOURCE = Field(
        field_name="event_source",
        alias_name="event_source",
        description=gettext_lazy("事件来源"),
        field_type=FIELD_TYPE_STRING,
        option=dict(),
        is_dimension=False,
    )

    OPERATOR = Field(
        field_name="operator",
        alias_name="operator",
        description=gettext_lazy("责任人"),
        field_type=FIELD_TYPE_TEXT,
        is_text=True,
        is_analyzed=True,
        option=dict(),
        is_dimension=False,
    )


class RiskStatus(TextChoices):
    """
    所有风险状态

    ```mermaid
    graph TB
    A(风险单产生 NEW)
    B(自动处理审批中 FOR_APPROVE)
    C(套餐处理中(自动) AUTO_PROCESS)
    D(已关单 CLOSED)
    E(待处理 AWAIT_PROCESS)
    F(套餐处理中(人工发起) AUTO_PROCESS)
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

    # 录入中, 手工录入风险才存在这个状态，同步到BKBase后自动切换为NEW
    STAND_BY = "stand_by", gettext_lazy("录入中")

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

    ALL = "all", gettext_lazy("全部风险")
    TODO = "todo", gettext_lazy("待我处理")
    WATCH = "watch", gettext_lazy("我的关注")


class RiskEventSubscriptionFieldCategory(TextChoices):
    """
    风险事件订阅字段所属类别
    """

    EVENT = "event", gettext_lazy("事件")
    RISK = "risk", gettext_lazy("风险")
    STRATEGY = "strategy", gettext_lazy("策略")
    STRATEGY_TAG = "strategy_tag", gettext_lazy("策略标签")


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


class RiskMetaFields:
    """
    风险元信息字段（用于策略配置中的风险字段展示）
    """

    @property
    def fields(self):
        return [
            # 1 风险ID
            self.RISK_ID,
            # 2 风险等级
            self.RISK_LEVEL,
            # 3 风险类型
            self.RISK_TYPE,
            # 4 风险标签
            self.RISK_TAGS,
            # 5 风险命中策略
            self.STRATEGY_NAME,
            # 9 处理状态
            self.PROCESSING_STATUS,
            # 10 责任人
            self.RESPONSIBLE_PERSON,
            # 11 当前处理人
            self.ASSIGNED_TO,
            # 12 关注人
            self.FOLLOWERS,
            # 13 首次发现时间
            self.EVENT_TIME,
            # 14 最后发现时间
            self.EVENT_END_TIME,
            # 15 最后一次处理时间
            self.LAST_OPERATE_TIME,
            # 16 风险标记
            self.RISK_LABEL,
            # 17 处理规则
            self.PROCESSING_RULE,
            # 6 风险描述
            self.RISK_DESCRIPTION,
            # 7 风险危害
            self.RISK_HAZARD,
            # 8 处理指引
            self.RISK_GUIDANCE,
        ]

    RISK_LEVEL = Field(
        field_name="risk_level",
        alias_name="risk_level",
        description=gettext_lazy("风险等级"),
        field_type=FIELD_TYPE_STRING,
        option=dict(),
    )

    RISK_ID = Field(
        field_name="risk_id",
        alias_name="risk_id",
        description=gettext_lazy("风险ID"),
        field_type=FIELD_TYPE_STRING,
        option=dict(),
    )

    RISK_DESCRIPTION = Field(
        field_name="event_content",
        alias_name="risk_description",
        description=gettext_lazy("风险描述"),
        field_type=FIELD_TYPE_TEXT,
        is_analyzed=True,
        is_text=True,
        option=dict(),
        is_required=False,
    )

    RISK_TAGS = Field(
        field_name="risk_tags",
        alias_name="risk_tags",
        description=gettext_lazy("风险标签"),
        field_type=FIELD_TYPE_TEXT,
        is_analyzed=True,
        is_text=True,
        option=dict(),
        is_required=False,
    )

    RISK_TYPE = Field(
        field_name="event_type",
        alias_name="risk_type",
        description=gettext_lazy("风险类型"),
        field_type=FIELD_TYPE_TEXT,
        is_required=False,
        is_analyzed=True,
        is_text=True,
        option=dict(),
    )

    STRATEGY_NAME = Field(
        field_name="strategy_name",
        alias_name="strategy_name",
        description=gettext_lazy("风险命中策略"),
        field_type=FIELD_TYPE_STRING,
        option=dict(),
    )

    RISK_HAZARD = Field(
        field_name="risk_hazard",
        alias_name="risk_hazard",
        description=gettext_lazy("风险危害"),
        field_type=FIELD_TYPE_TEXT,
        is_analyzed=True,
        is_text=True,
        option=dict(),
        is_required=False,
    )

    RISK_GUIDANCE = Field(
        field_name="risk_guidance",
        alias_name="risk_guidance",
        description=gettext_lazy("处理指引"),
        field_type=FIELD_TYPE_TEXT,
        is_analyzed=True,
        is_text=True,
        option=dict(),
        is_required=False,
    )

    PROCESSING_STATUS = Field(
        field_name="status",
        alias_name="status",
        description=gettext_lazy("处理状态"),
        field_type=FIELD_TYPE_STRING,
        option=dict(),
    )

    PROCESSING_RULE = Field(
        field_name="rule_id",
        alias_name="rule_id",
        description=gettext_lazy("处理规则"),
        field_type=FIELD_TYPE_LONG,
        option=dict(),
    )

    RESPONSIBLE_PERSON = Field(
        field_name="operator",
        alias_name="operator",
        description=gettext_lazy("责任人"),
        field_type=FIELD_TYPE_TEXT,
        is_text=True,
        is_analyzed=True,
        option=dict(),
    )

    ASSIGNED_TO = Field(
        field_name="current_operator",
        alias_name="current_operator",
        description=gettext_lazy("当前处理人"),
        field_type=FIELD_TYPE_TEXT,
        is_text=True,
        is_analyzed=True,
        option=dict(),
    )

    FOLLOWERS = Field(
        field_name="notice_users",
        alias_name="notice_users",
        description=gettext_lazy("关注人"),
        field_type=FIELD_TYPE_TEXT,
        is_text=True,
        is_analyzed=True,
        option=dict(),
    )

    EVENT_TIME = Field(
        field_name="event_time",
        alias_name="event_time",
        description=gettext_lazy("首次发现时间"),
        field_type=FIELD_TYPE_LONG,
        option={"time_zone": DEFAULT_TIME_ZONE, "time_format": TRANSFER_TIME_FORMAT},
        is_time=True,
    )

    EVENT_END_TIME = Field(
        field_name="event_end_time",
        alias_name="event_end_time",
        description=gettext_lazy("最后发现时间"),
        field_type=FIELD_TYPE_LONG,
        option={"time_zone": DEFAULT_TIME_ZONE, "time_format": TRANSFER_TIME_FORMAT},
        is_time=True,
    )

    LAST_OPERATE_TIME = Field(
        field_name="last_operate_time",
        alias_name="last_operate_time",
        description=gettext_lazy("最后一次处理时间"),
        field_type=FIELD_TYPE_LONG,
        option={"time_zone": DEFAULT_TIME_ZONE, "time_format": TRANSFER_TIME_FORMAT},
        is_time=True,
    )

    RISK_LABEL = Field(
        field_name="risk_label",
        alias_name="risk_label",
        description=gettext_lazy("风险标记"),
        field_type=FIELD_TYPE_STRING,
        option=dict(),
    )


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


class RiskExportField(TextChoices):
    """
    定义风险基础信息字段及其对应的显示名称
    """

    RISK_ID = "risk_id", gettext_lazy("风险ID")
    RISK_TITLE = "risk_title", gettext_lazy("风险标题")
    EVENT_CONTENT = "event_content", gettext_lazy("风险描述")
    RISK_TAGS = "risk_tags", gettext_lazy("风险标签")
    EVENT_TYPE = "event_type", gettext_lazy("风险类型")
    RISK_LEVEL = "risk_level", gettext_lazy("风险等级")
    STRATEGY_NAME = "strategy_name", gettext_lazy("风险命中策略")
    STRATEGY_ID = "strategy_id", gettext_lazy("风险命中策略ID")
    RAW_EVENT_ID = "raw_event_id", gettext_lazy("原始事件ID")
    EVENT_END_TIME = "event_end_time", gettext_lazy("最后发现时间")
    EVENT_TIME = "event_time", gettext_lazy("首次发现时间")
    RISK_HAZARD = "risk_hazard", gettext_lazy("风险危害")
    RISK_GUIDANCE = "risk_guidance", gettext_lazy("处理指引")
    STATUS = "status", gettext_lazy("处理状态")
    RULE_ID = "rule_id", gettext_lazy("处理规则")
    OPERATOR = "operator", gettext_lazy("责任人")
    CURRENT_OPERATOR = "current_operator", gettext_lazy("当前处理人")
    NOTICE_USERS = "notice_users", gettext_lazy("关注人")

    @classmethod
    def export_fields(cls) -> List[ExportField]:
        return [ExportField(raw_name=field.value, display_name=str(field.label)) for field in cls]


# 事件导出字段前缀
EVENT_EXPORT_FIELD_PREFIX = "event."
# 风险导出文件名模板
RISK_EXPORT_FILE_NAME_TMP = gettext_lazy("审计风险_{risk_view_type}_{datetime}.xlsx")


@register_choices("event_filter_operator")
class EventFilterOperator(TextChoices):
    """
    事件筛选操作符
    """

    EQUAL = "=", gettext_lazy("=")
    CONTAINS = "CONTAINS", gettext_lazy("包含")
    IN = "IN", gettext_lazy("IN")
    NOT_EQUAL = "!=", gettext_lazy("!=")
    NOT_CONTAINS = "NOT CONTAINS", gettext_lazy("不包含")
    NOT_IN = "NOT IN", gettext_lazy("NOT IN")
    GREATER_THAN_EQUAL = ">=", gettext_lazy(">=")
    LESS_THAN_EQUAL = "<=", gettext_lazy("<=")
    GREATER_THAN = ">", gettext_lazy(">")
    LESS_THAN = "<", gettext_lazy("<")


# 风险等级排序字段
RISK_LEVEL_ORDER_FIELD = "strategy__risk_level"


class RenderTaskStatus(TextChoices):
    """
    渲染任务状态
    """

    PENDING = "pending", gettext_lazy("待处理")
    PROCESSING = "processing", gettext_lazy("处理中")
    COMPLETED = "completed", gettext_lazy("已完成")
    FAILED = "failed", gettext_lazy("失败")
    ABANDONED = "abandoned", gettext_lazy("已放弃")


class RiskReportStatus(TextChoices):
    """
    风险报告状态
    """

    AUTO = "auto", gettext_lazy("自动生成")
    MANUAL = "manual", gettext_lazy("人工编辑")


@register_choices("aggregation_function")
class AggregationFunction(TextChoices):
    """
    聚合函数枚举

    用于报告模板中事件变量的聚合计算。
    """

    SUM = "sum", gettext_lazy("求和")
    AVG = "avg", gettext_lazy("平均值")
    MAX = "max", gettext_lazy("最大值")
    MIN = "min", gettext_lazy("最小值")
    COUNT = "count", gettext_lazy("计数")
    COUNT_DISTINCT = "count_distinct", gettext_lazy("去重计数")
    LATEST = "latest", gettext_lazy("最新值")
    FIRST = "first", gettext_lazy("首次值")
    LIST = "list", gettext_lazy("列表")
    LIST_DISTINCT = "list_distinct", gettext_lazy("去重列表")

    @classmethod
    def get_supported_field_types(cls, agg_func: str) -> List[str]:
        """
        获取聚合函数支持的字段类型

        Args:
            agg_func: 聚合函数名称

        Returns:
            支持的字段类型列表，空列表表示支持所有类型
        """
        from api.bk_base.constants import BkBaseFieldType

        numeric_types = [
            BkBaseFieldType.INT,
            BkBaseFieldType.LONG,
            BkBaseFieldType.FLOAT,
            BkBaseFieldType.DOUBLE,
        ]
        numeric_and_timestamp_types = numeric_types + [BkBaseFieldType.TIMESTAMP]

        type_mapping = {
            cls.SUM: numeric_types,
            cls.AVG: numeric_types,
            cls.MAX: numeric_and_timestamp_types,
            cls.MIN: numeric_and_timestamp_types,
            # 以下函数支持所有类型，返回空列表
            cls.COUNT: [],
            cls.COUNT_DISTINCT: [],
            cls.LATEST: [],
            cls.FIRST: [],
            cls.LIST: [],
            cls.LIST_DISTINCT: [],
        }
        return type_mapping.get(agg_func, [])


# 报告风险变量列表
# 用于模板中引用风险字段，如 {{ risk.risk_id }}
REPORT_RISK_VARIABLES = [
    {"field": "risk_id", "name": gettext_lazy("风险ID"), "description": gettext_lazy("风险单唯一标识")},
    {"field": "title", "name": gettext_lazy("风险标题"), "description": gettext_lazy("风险单标题")},
    {"field": "risk_level", "name": gettext_lazy("风险等级"), "description": gettext_lazy("风险等级标签")},
    {"field": "event_time", "name": gettext_lazy("首次发现时间"), "description": ""},
    {"field": "event_end_time", "name": gettext_lazy("最后发现时间"), "description": ""},
    {"field": "event_content", "name": gettext_lazy("事件内容"), "description": gettext_lazy("首个事件的内容摘要")},
    {"field": "operator", "name": gettext_lazy("责任人"), "description": gettext_lazy("风险相关的责任人列表")},
    {"field": "status", "name": gettext_lazy("风险状态"), "description": ""},
    {"field": "risk_label", "name": gettext_lazy("风险标签"), "description": ""},
    {"field": "strategy_id", "name": gettext_lazy("命中策略ID"), "description": ""},
    {"field": "strategy_name", "name": gettext_lazy("命中策略名称"), "description": ""},
    {"field": "risk_hazard", "name": gettext_lazy("风险危害"), "description": gettext_lazy("来自策略配置")},
    {"field": "risk_guidance", "name": gettext_lazy("处理指引"), "description": gettext_lazy("来自策略配置")},
]
