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

from django.utils.translation import gettext

from apps.permission.constants import IAMSystems
from apps.permission.handlers.actions.base import ActionMeta
from apps.permission.handlers.resource_types import ResourceEnum
from apps.permission.handlers.version import BkLogPermissionVersion


class ActionEnum:
    SEARCH_REGULAR_EVENT = ActionMeta(
        id="search_regular_event",
        name=gettext("审计日志检索"),
        name_en="Search Audit Event",
        type="view",
        related_resource_types=[ResourceEnum.SYSTEM],
        related_actions=[],
        version=1,
    )

    ACCESS_AUDIT_SENSITIVE_INFO = ActionMeta(
        id="access_audit_sensitive_info",
        name=gettext("审计敏感信息查看"),
        name_en="Access Audit Sensitive Info",
        type="view",
        related_resource_types=[ResourceEnum.SENSITIVE_OBJECT],
        related_actions=[],
        version=1,
    )

    # 系统接入
    CREATE_SYSTEM = ActionMeta(
        id="create_system",
        name=gettext("系统创建"),
        name_en="Create System",
        type="create",
        related_resource_types=[],
        related_actions=[],
        version=1,
    )
    LIST_SYSTEM = ActionMeta(
        id="list_system",
        name=gettext("系统列表访问"),
        name_en="List System",
        type="view",
        related_resource_types=[],
        related_actions=[],
        version=1,
    )
    VIEW_SYSTEM = ActionMeta(
        id="view_system",
        name=gettext("系统查看"),
        name_en="View System",
        type="view",
        related_resource_types=[ResourceEnum.SYSTEM],
        related_actions=[],
        version=1,
    )
    EDIT_SYSTEM = ActionMeta(
        id="edit_system",
        name=gettext("系统编辑"),
        name_en="Edit System",
        type="edit",
        related_resource_types=[ResourceEnum.SYSTEM],
        related_actions=[],
        version=1,
    )
    # 数据存储

    LIST_STORAGE = ActionMeta(
        id="list_storage",
        name=gettext("数据存储列表访问"),
        name_en="List Storage",
        type="view",
        related_resource_types=[],
        related_actions=[],
        version=1,
    )
    VIEW_STORAGE = ActionMeta(
        id="view_storage",
        name=gettext("数据存储查看"),
        name_en="View Storage",
        type="view",
        related_resource_types=[],
        related_actions=[],
        version=1,
    )
    CREATE_STORAGE = ActionMeta(
        id="create_storage",
        name=gettext("数据存储创建"),
        name_en="Create Storage",
        type="create",
        related_resource_types=[],
        related_actions=[],
        version=1,
    )
    EDIT_STORAGE = ActionMeta(
        id="edit_storage",
        name=gettext("数据存储编辑"),
        name_en="Edit Storage",
        type="edit",
        related_resource_types=[],
        related_actions=[],
        version=1,
    )
    DELETE_STORAGE = ActionMeta(
        id="delete_storage",
        name=gettext("数据存储删除"),
        name_en="Delete Storage",
        type="delete",
        related_resource_types=[],
        related_actions=[],
        version=1,
    )

    # 敏感对象管理
    LIST_SENSITIVE_OBJECT = ActionMeta(
        id="list_sensitive_object",
        name=gettext("敏感信息对象列表"),
        name_en="List SENSITIVE OBJECT",
        type="view",
        related_resource_types=[],
        related_actions=[],
        version=1,
    )

    # 全局设置
    ACCESS_GLOBAL_SETTING = ActionMeta(
        id="access_global_setting",
        name=gettext("全局设置查看"),
        name_en="View Global Setting",
        type="view",
        related_resource_types=[],
        related_actions=[],
        version=1,
    )
    MANAGE_GLOBAL_SETTING = ActionMeta(
        id="manage_global_setting",
        name=gettext("全局设置管理"),
        name_en="Manage Global Setting",
        type="manage",
        related_resource_types=[],
        related_actions=[],
        version=1,
    )

    # 平台管理
    MANAGE_PLATFORM = ActionMeta(
        id="manage_platform",
        name=gettext("平台管理"),
        name_en="Manage Platform",
        type="manage",
        related_resource_types=[],
        related_actions=[],
        version=1,
    )

    # 场景管理
    VIEW_SCENE = ActionMeta(
        id="view_scene",
        name=gettext("查看场景"),
        name_en="View Scene",
        type="view",
        related_resource_types=[ResourceEnum.SCENE],
        related_actions=[],
        version=1,
    )
    MANAGE_SCENE = ActionMeta(
        id="manage_scene",
        name=gettext("管理场景"),
        name_en="Manage Scene",
        type="manage",
        related_resource_types=[ResourceEnum.SCENE],
        # 注意：VIEW_SCENE 也在本文件定义，但不构成前向引用（类属性赋值时已可用）
        related_actions=[VIEW_SCENE],
        version=1,
    )

    # 策略分析
    LIST_STRATEGY = ActionMeta(
        id="list_strategy_v2",
        name=gettext("策略列表访问(V2)"),
        name_en="List Strategy(V2)",
        type="list",
        related_resource_types=[ResourceEnum.SCENE],
        related_actions=[MANAGE_SCENE],
        version=1,
    )
    CREATE_STRATEGY = ActionMeta(
        id="create_strategy_v2",
        name=gettext("创建策略(V2)"),
        name_en="Create Strategy(V2)",
        type="create",
        related_resource_types=[ResourceEnum.SCENE],
        # related_actions 在下方 _patch_related_actions 中补齐（含 LIST_NOTICE_GROUP、LIST_LINK_TABLE 前向引用）
        related_actions=[MANAGE_SCENE],
        version=1,
    )
    GENERATE_STRATEGY_RISK = ActionMeta(
        id="generate_strategy_risk",
        name=gettext("手工生成策略风险"),
        name_en="Generate Strategy Risk",
        type="create",
        related_resource_types=[ResourceEnum.STRATEGY],
        # related_actions 在下方 _patch_related_actions 中补齐（含 LIST_NOTICE_GROUP 前向引用）
        related_actions=[MANAGE_SCENE, LIST_STRATEGY],
        version=1,
    )
    EDIT_STRATEGY = ActionMeta(
        id="edit_strategy",
        name=gettext("编辑策略"),
        name_en="Edit Strategy",
        type="edit",
        related_resource_types=[ResourceEnum.STRATEGY],
        # related_actions 在下方 _patch_related_actions 中补齐（含 LIST_NOTICE_GROUP、LIST_LINK_TABLE、PROCESS_RISK 前向引用）
        related_actions=[MANAGE_SCENE, LIST_STRATEGY, GENERATE_STRATEGY_RISK],
        version=1,
    )
    DELETE_STRATEGY = ActionMeta(
        id="delete_strategy",
        name=gettext("删除策略"),
        name_en="Delete Strategy",
        type="delete",
        related_resource_types=[ResourceEnum.STRATEGY],
        related_actions=[MANAGE_SCENE, LIST_STRATEGY],
        version=1,
    )
    # 联表
    LIST_LINK_TABLE = ActionMeta(
        id="list_link_table_v2",
        name=gettext("联表列表访问(V2)"),
        name_en="List Link Table(V2)",
        type="list",
        related_resource_types=[ResourceEnum.SCENE],
        related_actions=[MANAGE_SCENE],
        version=1,
    )
    VIEW_LINK_TABLE = ActionMeta(
        id="view_link_table",
        name=gettext("查看联表"),
        name_en="View Link Table",
        type="view",
        related_resource_types=[ResourceEnum.LINK_TABLE],
        related_actions=[MANAGE_SCENE, LIST_LINK_TABLE],
        version=1,
    )
    CREATE_LINK_TABLE = ActionMeta(
        id="create_link_table_v2",
        name=gettext("创建联表(V2)"),
        name_en="Create Link Table(V2)",
        type="create",
        related_resource_types=[ResourceEnum.SCENE],
        related_actions=[MANAGE_SCENE, LIST_LINK_TABLE],
        version=1,
    )
    EDIT_LINK_TABLE = ActionMeta(
        id="edit_link_table",
        name=gettext("编辑联表"),
        name_en="Edit Link Table",
        type="edit",
        related_resource_types=[ResourceEnum.LINK_TABLE],
        related_actions=[MANAGE_SCENE, VIEW_LINK_TABLE],
        version=1,
    )
    DELETE_LINK_TABL = ActionMeta(
        id="delete_link_table",
        name=gettext("删除联表"),
        name_en="Delete Link Table",
        type="delete",
        related_resource_types=[ResourceEnum.LINK_TABLE],
        related_actions=[MANAGE_SCENE, VIEW_LINK_TABLE],
        version=1,
    )
    LIST_RISK = ActionMeta(
        id="list_risk_v2",
        name=gettext("审计风险列表(V2)"),
        name_en="List Risk (V2)",
        type="list",
        related_resource_types=[ResourceEnum.RISK],
        related_actions=[],
        version=1,
    )
    EDIT_RISK = ActionMeta(
        id="edit_risk_v2",
        name=gettext("编辑审计风险(V2)"),
        name_en="Manage Risk (V2)",
        type="manage",
        related_resource_types=[ResourceEnum.RISK],
        related_actions=[],
        version=1,
    )
    PROCESS_RISK = ActionMeta(
        id="process_risk",
        name=gettext("处理审计风险"),
        name_en="Process Risk",
        type="manage",
        related_resource_types=[ResourceEnum.RISK],
        related_actions=[],
        version=1,
    )
    LIST_RULE = ActionMeta(
        id="list_rule_v2",
        name=gettext("规则列表访问(V2)"),
        name_en="List Rule(V2)",
        type="list",
        related_resource_types=[ResourceEnum.SCENE],
        related_actions=[MANAGE_SCENE],
        version=1,
    )
    CREATE_RULE = ActionMeta(
        id="create_rule_v2",
        name=gettext("新建规则(V2)"),
        name_en="Create Rule(V2)",
        type="create",
        related_resource_types=[ResourceEnum.SCENE],
        related_actions=[MANAGE_SCENE, LIST_RULE],
        version=1,
    )
    EDIT_RULE = ActionMeta(
        id="edit_rule_v2",
        name=gettext("编辑规则(V2)"),
        name_en="Edit Rule(V2)",
        type="edit",
        related_resource_types=[ResourceEnum.SCENE],
        related_actions=[MANAGE_SCENE, LIST_RULE],
        version=1,
    )
    DELETE_RULE = ActionMeta(
        id="delete_rule_v2",
        name=gettext("删除规则(V2)"),
        name_en="Delete Rule(V2)",
        type="delete",
        related_resource_types=[ResourceEnum.SCENE],
        related_actions=[MANAGE_SCENE, LIST_RULE],
        version=1,
    )
    LIST_PA = ActionMeta(
        id="list_pa_v2",
        name=gettext("处理套餐列表(V2)"),
        name_en="List Tools(V2)",
        type="list",
        related_resource_types=[ResourceEnum.SCENE],
        related_actions=[MANAGE_SCENE],
        version=1,
    )
    CREATE_PA = ActionMeta(
        id="create_pa_v2",
        name=gettext("创建处理套餐(V2)"),
        name_en="Create Tool(V2)",
        type="create",
        related_resource_types=[ResourceEnum.SCENE],
        related_actions=[MANAGE_SCENE, LIST_PA],
        version=1,
    )
    EDIT_PA = ActionMeta(
        id="edit_pa_v2",
        name=gettext("编辑处理套餐(V2)"),
        name_en="Edit Tool(V2)",
        type="edit",
        related_resource_types=[ResourceEnum.SCENE],
        related_actions=[MANAGE_SCENE, LIST_PA],
        version=1,
    )
    LIST_NOTICE_GROUP = ActionMeta(
        id="list_notice_group_v2",
        name=gettext("通知组列表(V2)"),
        name_en="List Notice Group(V2)",
        type="list",
        related_resource_types=[ResourceEnum.SCENE],
        related_actions=[MANAGE_SCENE],
        version=1,
    )
    CREATE_NOTICE_GROUP = ActionMeta(
        id="create_notice_group_v2",
        name=gettext("新建通知组(V2)"),
        name_en="Create Notice Group(V2)",
        type="create",
        related_resource_types=[ResourceEnum.SCENE],
        related_actions=[MANAGE_SCENE, LIST_NOTICE_GROUP],
        version=1,
    )
    EDIT_NOTICE_GROUP_V2 = ActionMeta(
        id="edit_notice_group_v2",
        name=gettext("编辑通知组(V2)"),
        name_en="Edit Notice Group V2",
        type="edit",
        related_resource_types=[ResourceEnum.NOTICE_GROUP],
        related_actions=[MANAGE_SCENE, LIST_NOTICE_GROUP],
        version=1,
    )
    DELETE_NOTICE_GROUP_V2 = ActionMeta(
        id="delete_notice_group_v2",
        name=gettext("删除通知组(V2)"),
        name_en="Delete Notice Group V2",
        type="delete",
        related_resource_types=[ResourceEnum.NOTICE_GROUP],
        related_actions=[MANAGE_SCENE, LIST_NOTICE_GROUP],
        version=1,
    )
    LIST_BASE_PANEL = ActionMeta(
        id="list_base_panel",
        name=gettext("报表列表"),
        name_en="List Base Panel",
        type="list",
        related_resource_types=[],
        related_actions=[],
        version=1,
    )
    VIEW_BASE_PANEL = ActionMeta(
        id="view_base_panel_v2",
        name=gettext("查看报表"),
        name_en="View Audit Report",
        type="view",
        related_resource_types=[ResourceEnum.PANEL],
        related_actions=[],
        version=1,
    )
    VIEW_PANEL = ActionMeta(
        id="view_panel",
        name=gettext("查看报表(组织架构)"),
        name_en="View Audit Report by Department",
        type="view",
        related_resource_types=[ResourceEnum.DEPT_BK_USERMGR],
        related_actions=[LIST_BASE_PANEL, VIEW_BASE_PANEL],
        version=1,
    )
    VIEW_TAG_PANEL = ActionMeta(
        id="view_tag_panel",
        name=gettext("查看报表(标签)"),
        name_en="View Audit Report by Tag",
        type="view",
        related_resource_types=[ResourceEnum.TAG],
        related_actions=[LIST_BASE_PANEL, VIEW_BASE_PANEL],
        version=1,
    )

    # 系统诊断
    VIEW_SYSTEM_DIAGNOSIS_PANEL = ActionMeta(
        id="view_system_diagnosis_panel",
        name=gettext("系统诊断报表查看"),
        name_en="View System Diagnosis Panel",
        type="view",
        related_resource_types=[ResourceEnum.SYSTEM],
        related_actions=[LIST_BASE_PANEL, VIEW_BASE_PANEL],
        version=1,
    )
    # 查看场景视图
    VIEW_SCENARIO_PANEL = ActionMeta(
        id="view_scenario_panel",
        name=gettext("查看场景视图"),
        name_en="View Scenario Panel",
        type="view",
        related_resource_types=[ResourceEnum.TAG],
        related_actions=[LIST_BASE_PANEL, VIEW_BASE_PANEL],
        version=1,
    )
    USE_TOOL = ActionMeta(
        id="use_tool",
        name=gettext("使用工具"),
        name_en="Use Tool",
        type="view",
        related_resource_types=[ResourceEnum.TOOL],
        related_actions=[],
        version=1,
    )
    USE_TOOL_BY_TAG = ActionMeta(
        id="use_tool_by_tag",
        name=gettext("使用工具(标签)"),
        name_en="Use Tool by Tag",
        type="view",
        related_resource_types=[ResourceEnum.TAG],
        related_actions=[],
        version=1,
    )
    MANAGE_TOOL = ActionMeta(
        id="manage_tool",
        name=gettext("管理工具"),
        name_en="Manage Tool",
        type="edit",
        related_resource_types=[ResourceEnum.TOOL],
        related_actions=[],
        version=1,
        description="管理工具,包含工具的编辑、删除操作",
        description_en="Manage Tool,including tool editing and deletion",
    )
    MANAGE_TOOL_BY_TAG = ActionMeta(
        id="manage_tool_by_tag",
        name=gettext("管理工具(标签)"),
        name_en="Manage Tool by Tag",
        type="edit",
        related_resource_types=[ResourceEnum.TAG],
        related_actions=[],
        version=1,
        description="管理工具(标签),包含工具的编辑、删除操作",
        description_en="Manage Tool(Tag),including tool editing and deletion",
    )

    # 日志平台
    CREATE_COLLECTION_BK_LOG = ActionMeta(
        id=BkLogPermissionVersion("create_collection").action_id,
        name=gettext("采集新建"),
        name_en="Create Collection",
        type="create",
        related_resource_types=BkLogPermissionVersion("create_collection").related_resource_types,
        related_actions=[],
        version=1,
        system_id=IAMSystems.BK_LOG.value,
    )
    VIEW_COLLECTION_BK_LOG = ActionMeta(
        id=BkLogPermissionVersion("view_collection").action_id,
        name=gettext("采集查看"),
        name_en="View Collection",
        type="view",
        related_resource_types=[ResourceEnum.COLLECTION_BK_LOG],
        related_actions=[],
        version=1,
        system_id=IAMSystems.BK_LOG.value,
    )
    MANAGE_COLLECTION_BK_LOG = ActionMeta(
        id=BkLogPermissionVersion("manage_collection").action_id,
        name=gettext("采集管理"),
        name_en="Manage Collection",
        type="manage",
        related_resource_types=[ResourceEnum.COLLECTION_BK_LOG],
        related_actions=[],
        version=1,
        system_id=IAMSystems.BK_LOG.value,
    )
    VIEW_BUSINESS_BK_LOG = ActionMeta(
        id=BkLogPermissionVersion("view_business").action_id,
        name=gettext("业务访问"),
        name_en="View Business",
        type="view",
        related_resource_types=BkLogPermissionVersion("view_business").related_resource_types,
        related_actions=[],
        version=1,
        system_id=IAMSystems.BK_LOG.value,
    )
    # bkvision
    VIEW_SHARE_BKVISION = ActionMeta(
        id="view_share",
        name=gettext("查看嵌入分享"),
        name_en="View Share",
        type="view",
        related_resource_types=[ResourceEnum.SHARE_BK_VISION],
        version=1,
        system_id=IAMSystems.BK_VISION.value,
    )

    @classmethod
    def choices(cls):
        """生成 Django 模型 choices 需要的格式: [(id1, name1), (id2, name2), ...]"""
        return [
            (action.id, action.name)
            for name, action in vars(cls).items()
            if not name.startswith('_') and isinstance(action, ActionMeta)
        ]


# 补齐存在前向引用的 related_actions（在类定义完成后执行）
_CREATE_STRATEGY_EXTRA = [ActionEnum.LIST_STRATEGY, ActionEnum.LIST_NOTICE_GROUP, ActionEnum.LIST_LINK_TABLE]
ActionEnum.CREATE_STRATEGY.related_actions.extend(_CREATE_STRATEGY_EXTRA)

_GENERATE_STRATEGY_RISK_EXTRA = [ActionEnum.LIST_NOTICE_GROUP]
ActionEnum.GENERATE_STRATEGY_RISK.related_actions.extend(_GENERATE_STRATEGY_RISK_EXTRA)

_EDIT_STRATEGY_EXTRA = [
    ActionEnum.LIST_NOTICE_GROUP,
    ActionEnum.LIST_LINK_TABLE,
    ActionEnum.PROCESS_RISK,
]
ActionEnum.EDIT_STRATEGY.related_actions.extend(_EDIT_STRATEGY_EXTRA)
