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

from apps.permission.exceptions import ResourceNotExistError
from apps.permission.handlers.resource_types.base import ResourceTypeMeta
from apps.permission.handlers.resource_types.biz_bk_log import BusinessBKLog, SpaceBKLog
from apps.permission.handlers.resource_types.bk_vision import ShareBkVision
from apps.permission.handlers.resource_types.collection_bk_log import CollectionBKLog
from apps.permission.handlers.resource_types.dept_bk_usermgr import DeptBKUsermgr
from apps.permission.handlers.resource_types.notice_group import NoticeGroup
from apps.permission.handlers.resource_types.panel import Panel
from apps.permission.handlers.resource_types.risk import (
    ManualEvent,
    Risk,
    TicketNode,
    TicketPermission,
)
from apps.permission.handlers.resource_types.sensitive_object import (
    SensitiveAction,
    SensitiveObject,
    SensitiveResourceType,
)
from apps.permission.handlers.resource_types.strategy import (
    LinkTable,
    Strategy,
    StrategyTag,
)
from apps.permission.handlers.resource_types.system import System
from apps.permission.handlers.resource_types.tag import Tag
from apps.permission.handlers.resource_types.tool import Tool


class ResourceEnum:
    """
    资源类型枚举
    """

    SYSTEM = System
    SENSITIVE_OBJECT = SensitiveObject
    SENSITIVE_ACTION = SensitiveAction
    SENSITIVE_RESOURCE_TYPE = SensitiveResourceType
    STRATEGY = Strategy
    STRATEGY_TAG = StrategyTag
    LINK_TABLE = LinkTable
    NOTICE_GROUP = NoticeGroup
    RISK = Risk
    MANUAL_EVENT = ManualEvent
    TICKET_PERMISSION = TicketPermission
    TICKET_NODE = TicketNode
    PANEL = Panel
    TAG = Tag
    TOOL = Tool
    # BK LOG
    SPACE_BK_LOG = SpaceBKLog
    BUSINESS_BK_LOG = BusinessBKLog
    COLLECTION_BK_LOG = CollectionBKLog
    # BK User
    DEPT_BK_USERMGR = DeptBKUsermgr
    # BK Vision
    SHARE_BK_VISION = ShareBkVision


_all_resources = {resource.id: resource for resource in ResourceEnum.__dict__.values() if hasattr(resource, "id")}


def get_resource_by_id(resource_id: str) -> ResourceTypeMeta:
    """
    根据资源ID获取资源
    """
    if resource_id not in _all_resources:
        raise ResourceNotExistError(gettext("资源ID不存在：%(resource_id)s") % {"resource_id": resource_id})

    return _all_resources[resource_id]
