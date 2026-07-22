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

from apps.notice.constants import ADMIN_NOTICE_GROUP_ID
from core.choices import TextChoices

HEALTHZ_SPAN_NAME = "Healthz"
HEALTHZ_THROTTLE_SCOPE = "10/m"


class WebLinkEnum(TextChoices):
    WEB_LINK = "link", gettext_lazy("超链接")


INIT_ES_FISHED_KEY = "init_es_finished_check"
INIT_DORIS_FISHED_KEY = "init_doris_finished_check"
INIT_REDIS_FISHED_KEY = "init_redis_finished_check"
INIT_PLUGIN_FISHED_KEY = "init_plugin_finished_check"
INIT_SNAPSHOT_FINISHED_KEY = "init_snapshot_finished_check"
INIT_EVENT_FINISHED_KEY = "init_event_finished_check"
INIT_FIELDS_FINISHED_KEY = "init_fields_finished_check"
INIT_SYSTEM_FINISHED_KEY = "init_system_finished_check"
INIT_ASSET_FINISHED_KEY = "init_asset_finished_check"
INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY = "init_system_rule_audit_finished_check"
INIT_SDK_CONFIG_FINISHED_KEY = "init_sdk_config_finished_check"
INIT_DOC_CONFIG_FINISHED_KEY = "init_doc_config_finished_check"
INIT_AGENT_CONFIG_FINISHED_KEY = "init_agent_config_finished_check"

DEFAULT_QUERY_STRING_HELP_KEY = "query_string_help"
DEFAULT_QUERY_STRING_HELP_ENV_KEY = "BKAPP_QUERY_STRING_HELP"

DEFAULT_SCHEMA_HELP_KEY = "schema_help"
DEFAULT_SCHEMA_HELP = (
    "https://github.com/TencentBlueKing/iam-python-sdk/blob/master/docs/usage.md"
    "#31-resourceprovider-%E7%9A%84%E5%AE%9A%E4%B9%89"
)

TENCENT_WEB_FOOTER = [
    {
        "type": WebLinkEnum.WEB_LINK.value,
        "type_description": WebLinkEnum.WEB_LINK.label,
        "text": gettext_lazy("联系BK助手"),
        "url": "",
    },
    {
        "type": WebLinkEnum.WEB_LINK.value,
        "type_description": WebLinkEnum.WEB_LINK.label,
        "text": gettext_lazy("蓝鲸桌面"),
        "url": "",
    },
]

# IAM WEB 访问地址
IAM_WEB_URL_KEY = "iam_web_url"
# 互娱应用系统和敏感操作安全管理规范访问地址
IEG_STD_OP_DOC_URL_KEY = "ieg_std_op_doc_url"
# bkbase WEB 访问地址
BKBASE_WEB_URL_KEY = "bkbase_web_url"
# 检索规则 iwiki 地址
SEARCH_RULE_IWIKI_URL_KEY = "search_rule_iwiki_url"
# bkvision 分享权限申请地址
VISION_SHARE_PERMISSION_URL_KEY = "vision_share_permission_url"
# V3 系统新建地址
V3_SYSTEM_CREATE_URL_KEY = "v3_system_create_url"
# 检索规则 iwiki 地址
PERMISSION_MODEL_IWIKI_URL_KEY = "permission_model_iwiki_url"
# bkvision WEB 访问地址
BKVISION_WEB_URL_KEY = "bkvision_web_url"

SDK_CONFIG_KEY = "sdk_config"
AUDIT_DOC_CONFIG_KEY = "audit_doc_config"
PLATFORM_ADMIN_USERS_KEY = "platform_admin_users"
AGENT_AUTH_KEY = "agent_auth"

# AI 实践文档地址
AI_PRACTICES_KEY = "ai_practices"
DEFAULT_AI_PRACTICES = {"ai_summary": "http://example.com/wiki/"}


def get_manual_event_strategy_config(rt_id):
    """
    基于最新模板生成风险策略配置字典。
    保留所有字段数据，并将 rt_id 动态填入 SQL、DataSource、Select 配置以及 Where 条件中。

    Args:
        rt_id (str): 实时表ID (例如: '5000448_asset_bk_audit_risk')

    Returns:
        dict: 完整的配置字典
    """

    # 1. 动态构建 SQL 语句
    # 新版 SQL 使用了反引号 (`) 包裹表名和别名，我们需要在 f-string 中正确处理
    # 逻辑：子查询中 SELECT 的字段前缀、FROM 表名、WHERE 条件均需替换
    sql_statement = (
        f"SELECT `sub_table`.`u_020bf1f3c0b7812374031309d27c1e73` `event_data`,"
        f"`sub_table`.`u_e6ffe079ce9be342f287be948340991b` `strategy_id`,"
        f"`sub_table`.`u_2f606c22a8b8bec4d47242c235f8d2d9` `raw_event_id`,"
        f"`sub_table`.`u_0c5b77a14834daae88b98bacd7ce29db` `operator`,"
        f"`sub_table`.`u_46a4b7f4986ca8845bd00b56233756d7` `event_source`,"
        f"`sub_table`.`u_d76255b2e8d52f3c4af2ad50a692e1e2` `event_content`,"
        f"`sub_table`.`u_f974c8465fb8f678cf37a1be67f94e6e` `event_type`,"
        f"`sub_table`.`u_manual_event_id` `manual_event_id` "
        f"FROM (SELECT "
        f"`{rt_id}`.`event_content` `u_d76255b2e8d52f3c4af2ad50a692e1e2`,"
        f"`{rt_id}`.`raw_event_id` `u_2f606c22a8b8bec4d47242c235f8d2d9`,"
        f"`{rt_id}`.`strategy_id` `u_e6ffe079ce9be342f287be948340991b`,"
        f"`{rt_id}`.`event_evidence` `u_012fc82ec23cb93da97d18755de7aad9`,"
        f"`{rt_id}`.`event_type` `u_f974c8465fb8f678cf37a1be67f94e6e`,"
        f"`{rt_id}`.`event_data` `u_020bf1f3c0b7812374031309d27c1e73`,"
        f"`{rt_id}`.`event_time` `u_95a9c636484ff20d38642e088df195ca`,"
        f"`{rt_id}`.`event_source` `u_46a4b7f4986ca8845bd00b56233756d7`,"
        f"`{rt_id}`.`operator` `u_0c5b77a14834daae88b98bacd7ce29db`,"
        f"`{rt_id}`.`id` `u_manual_event_id` "
        f"FROM {rt_id} `{rt_id}` WHERE `{rt_id}`.`manual_synced` = 'false') `sub_table`"
    )

    # 2. 构建完整字典
    return {
        "tools": [],
        "created_by": "admin",
        "updated_at": "2025-11-20 11:48:47",
        "updated_by": "admin",
        "is_deleted": False,
        "namespace": "default",
        "strategy_name": "手动新建风险",
        "control_id": "",
        "control_version": None,
        "strategy_type": "rule",
        "configs": {
            "where": {"index": 0, "connector": "and", "conditions": []},
            "having": None,
            "select": [
                {
                    "keys": [],
                    "table": rt_id,  # 变量替换
                    "remark": "",
                    "raw_name": "event_content",
                    "aggregate": None,
                    "field_type": "string",
                    "display_name": "事件描述",
                },
                {
                    "keys": [],
                    "table": rt_id,  # 变量替换
                    "remark": "",
                    "raw_name": "raw_event_id",
                    "aggregate": None,
                    "field_type": "string",
                    "display_name": "原始事件ID",
                },
                {
                    "keys": [],
                    "table": rt_id,  # 变量替换
                    "remark": "",
                    "raw_name": "strategy_id",
                    "aggregate": None,
                    "field_type": "long",
                    "display_name": "策略ID",
                },
                {
                    "keys": [],
                    "table": rt_id,  # 变量替换
                    "remark": "",
                    "raw_name": "event_evidence",
                    "aggregate": None,
                    "field_type": "string",
                    "display_name": "事件证据",
                },
                {
                    "keys": [],
                    "table": rt_id,  # 变量替换
                    "remark": "",
                    "raw_name": "event_type",
                    "aggregate": None,
                    "field_type": "text",
                    "display_name": "事件类型",
                },
                {
                    "keys": [],
                    "table": rt_id,  # 变量替换
                    "remark": "",
                    "raw_name": "event_data",
                    "aggregate": None,
                    "field_type": "text",
                    "display_name": "事件拓展数据",
                },
                {
                    "keys": [],
                    "table": rt_id,  # 变量替换
                    "remark": "",
                    "raw_name": "event_time",
                    "aggregate": None,
                    "field_type": "string",
                    "display_name": "事件发生时间",
                },
                {
                    "keys": [],
                    "table": rt_id,  # 变量替换
                    "remark": "",
                    "raw_name": "event_source",
                    "aggregate": None,
                    "field_type": "string",
                    "display_name": "事件来源",
                },
                {
                    "keys": [],
                    "table": rt_id,  # 变量替换
                    "remark": "",
                    "raw_name": "operator",
                    "aggregate": None,
                    "field_type": "text",
                    "display_name": "责任人",
                },
                {
                    "keys": [],
                    "table": rt_id,  # 变量替换
                    "remark": "",
                    "raw_name": "id",
                    "aggregate": None,
                    "field_type": "long",
                    "display_name": "ID",
                },
            ],
            "config_type": "BuildIn",
            "data_source": {
                "rt_id": rt_id,  # 变量替换
                "link_table": None,
                "system_ids": [],
                "source_type": "stream_source",
                "display_name": rt_id,  # 变量替换
            },
        },
        "sql": sql_statement,  # 填入动态生成的 SQL
        "link_table_uid": None,
        "link_table_version": None,
        "status": "disabled",
        "notice_groups": [],
        "processor_groups": [ADMIN_NOTICE_GROUP_ID],
        "description": "自定义",
        "risk_level": "LOW",
        "risk_hazard": "自定义",
        "risk_guidance": "自定义",
        "risk_title": "Dummy",
        "event_basic_field_configs": [
            {
                "is_show": True,
                "field_name": "raw_event_id",
                "map_config": {"source_field": "原始事件ID"},
                "description": "系统会将原始事件ID相同的事件，关联至同一个未关闭的风险单据",
                "is_priority": True,
                "display_name": "原始事件ID",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "operator",
                "map_config": {"source_field": "责任人"},
                "description": "",
                "is_priority": True,
                "display_name": "责任人",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "event_time",
                "description": "",
                "is_priority": True,
                "display_name": "事件发生时间",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "event_source",
                "map_config": {"source_field": "事件来源"},
                "description": "",
                "is_priority": True,
                "display_name": "事件来源",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "strategy_id",
                "description": "",
                "is_priority": True,
                "display_name": "命中策略(ID)",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "event_content",
                "map_config": {"source_field": "事件描述"},
                "description": "",
                "is_priority": True,
                "display_name": "事件描述",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "event_type",
                "map_config": {"source_field": "事件类型"},
                "description": "",
                "is_priority": True,
                "display_name": "事件类型",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
        ],
        "event_data_field_configs": [
            {
                "is_show": True,
                "field_name": "事件描述",
                "description": "",
                "is_priority": False,
                "display_name": "事件描述",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "原始事件ID",
                "description": "",
                "is_priority": False,
                "display_name": "原始事件ID",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "策略ID",
                "description": "",
                "is_priority": False,
                "display_name": "策略ID",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "事件证据",
                "description": "",
                "is_priority": False,
                "display_name": "事件证据",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "事件类型",
                "description": "",
                "is_priority": False,
                "display_name": "事件类型",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "事件拓展数据",
                "description": "",
                "is_priority": False,
                "display_name": "事件拓展数据",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "事件发生时间",
                "description": "",
                "is_priority": False,
                "display_name": "事件发生时间",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "事件来源",
                "description": "",
                "is_priority": False,
                "display_name": "事件来源",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "责任人",
                "description": "",
                "is_priority": False,
                "display_name": "责任人",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
        ],
        "event_evidence_field_configs": [],
        "risk_meta_field_config": [
            {
                "is_show": True,
                "field_name": "risk_id",
                "description": "",
                "is_priority": True,
                "display_name": "风险ID",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "risk_level",
                "description": "",
                "is_priority": True,
                "display_name": "风险等级",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "event_type",
                "description": "",
                "is_priority": False,
                "display_name": "风险类型",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "risk_tags",
                "description": "",
                "is_priority": True,
                "display_name": "风险标签",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "strategy_name",
                "description": "",
                "is_priority": False,
                "display_name": "风险命中策略",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "status",
                "description": "",
                "is_priority": True,
                "display_name": "处理状态",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "operator",
                "description": "",
                "is_priority": False,
                "display_name": "责任人",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "current_operator",
                "description": "",
                "is_priority": True,
                "display_name": "当前处理人",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "notice_users",
                "description": "",
                "is_priority": False,
                "display_name": "关注人",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "event_time",
                "description": "",
                "is_priority": False,
                "display_name": "首次发现时间",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "event_end_time",
                "description": "",
                "is_priority": False,
                "display_name": "最后发现时间",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "last_operate_time",
                "description": "",
                "is_priority": False,
                "display_name": "最后一次处理时间",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "risk_label",
                "description": "",
                "is_priority": False,
                "display_name": "风险标记",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "rule_id",
                "description": "",
                "is_priority": False,
                "display_name": "处理规则",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "event_content",
                "description": "",
                "is_priority": False,
                "display_name": "风险描述",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "risk_hazard",
                "description": "",
                "is_priority": True,
                "display_name": "风险危害",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
            {
                "is_show": True,
                "field_name": "risk_guidance",
                "description": "",
                "is_priority": True,
                "display_name": "处理指引",
                "drill_config": [],
                "enum_mappings": {"mappings": []},
                "duplicate_field": False,
            },
        ],
        "is_formal": True,
        "source": "system",
    }
