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
from typing import Callable, Dict, List, Set, Union

from bk_resource import api, resource
from django.db.models import Q, QuerySet
from rest_framework.permissions import BasePermission

from apps.permission.handlers.actions import ActionEnum, ActionMeta
from apps.permission.handlers.drf import (
    InstanceActionPermission,
    wrapper_permission_field,
)
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from core.models import get_request_username
from services.web.common.caller_permission import should_skip_permission_from
from services.web.tool.converter import (
    ToolDjangoQuerySetConverter,
    ToolTagDjangoQuerySetConverter,
)
from services.web.tool.exceptions import (
    BkVisionSearchPermissionProhibited,
    ToolDoesNotExist,
)
from services.web.tool.models import Tool, ToolTag


def get_tool_permission_always_allowed_func(
    current_user: str, use_tool_permission_tags: Set[str], manage_tool_permission_tags: Set[str]
) -> Callable[[dict, str], bool]:
    """
    获取工具权限是否始终允许使用的函数
    :param current_user: 当前用户
    :param use_tool_permission_tags: 使用工具权限标签
    :param manage_tool_permission_tags: 管理工具权限标签
    :return: 工具权限是否始终允许使用的函数
    """

    def always_allowed_func(tool: dict, action_id: str) -> bool:
        if tool.get("created_by") == current_user:
            return True
        tags: Set[str] = set(tool["tags"])
        if action_id == ActionEnum.USE_TOOL.id:
            return bool(use_tool_permission_tags & tags)
        elif action_id == ActionEnum.MANAGE_TOOL.id:
            return bool(manage_tool_permission_tags & tags)
        else:
            return False

    return always_allowed_func


class ToolPermission:
    """
    工具权限类
    """

    def __init__(self, username: str):
        self.username = username
        self.permission = Permission(username)

    def fetch_tool_permission_tags(self, tool_tag_ids: List[int]) -> Dict[str, Set[str]]:
        """
        获取用户工具权限标签
        :param tool_tag_ids: 工具标签ID列表
        :return: 返回有权限的工具标签ID
        """

        use_tool_permission_tags = set()
        manage_tool_permission_tags = set()
        # 权限校验时资源类型需要携带资源实例，否则会报错
        if tool_tag_ids:
            permission_result: Dict[str, Dict[str, bool]] = resource.permission.batch_is_allowed(
                action_ids=[ActionEnum.USE_TOOL_BY_TAG.id, ActionEnum.MANAGE_TOOL_BY_TAG.id], resources=tool_tag_ids
            )
            for tag_id, permission in permission_result.items():
                if permission.get(ActionEnum.USE_TOOL_BY_TAG.id):
                    use_tool_permission_tags.add(str(tag_id))
                if permission.get(ActionEnum.MANAGE_TOOL_BY_TAG.id):
                    manage_tool_permission_tags.add(str(tag_id))
        return {
            "use_tool_permission_tags": use_tool_permission_tags,
            "manage_tool_permission_tags": manage_tool_permission_tags,
        }

    def wrapper_tool_permission_field(self, tool_list: List[dict], tool_tag_ids: List[int]):
        """
        包装工具权限字段
        :param tool_list: 工具列表
        :param tool_tag_ids: 工具标签ID列表
        :return: 工具列表
        """
        tool_tag_permission = self.fetch_tool_permission_tags(tool_tag_ids)
        use_tool_permission_tags = tool_tag_permission["use_tool_permission_tags"]
        manage_tool_permission_tags = tool_tag_permission["manage_tool_permission_tags"]
        always_allowed_func = get_tool_permission_always_allowed_func(
            current_user=self.username,
            use_tool_permission_tags=use_tool_permission_tags,
            manage_tool_permission_tags=manage_tool_permission_tags,
        )
        tool_list = wrapper_permission_field(
            result_list=tool_list,
            actions=[ActionEnum.USE_TOOL, ActionEnum.MANAGE_TOOL],
            id_field=lambda item: item["uid"],
            always_allowed=always_allowed_func,
        )
        return tool_list

    @property
    def local_tool_filter(self) -> Q:
        """
        获取本地工具筛选条件（即用户自己创建的工具）
        """
        return Q(created_by=self.username)

    def fetch_auth_tool_tags(
        self, action: Union[ActionEnum.USE_TOOL_BY_TAG, ActionEnum.MANAGE_TOOL_BY_TAG]
    ) -> QuerySet["ToolTag"]:
        """
        获取用户有权限的工具标签
        """

        policies = self.permission.get_policies_for_action(action=action)
        if not policies:
            return ToolTag.objects.none()
        tool_tag_q = ToolTagDjangoQuerySetConverter().convert(policies)
        return ToolTag.objects.filter(tool_tag_q).distinct()

    def get_tool_filter_by_tag_action(
        self, action: Union[ActionEnum.USE_TOOL_BY_TAG, ActionEnum.MANAGE_TOOL_BY_TAG]
    ) -> Q:
        """
        根据标签权限动作获取工具筛选条件
        """

        # 获取符合标签权限的工具 UID 列表
        tool_uids = self.fetch_auth_tool_tags(action).values_list('tool_uid', flat=True).distinct()
        return Q(uid__in=list(tool_uids))

    def get_tool_filter_by_tool_action(self, action: Union[ActionEnum.USE_TOOL, ActionEnum.MANAGE_TOOL]):
        """
        根据工具权限动作获取工具筛选条件
        """

        policies = self.permission.get_policies_for_action(action=action)
        if policies:
            return ToolDjangoQuerySetConverter().convert(policies)
        return Q()

    @property
    def authed_tool_filter(self) -> Q:
        """
        获取用户有权限的所有工具的组合筛选条件。

        权限组合逻辑:
        - 用户自己创建的工具
        - OR 用户有直接使用权限的工具
        - OR 用户有直接管理权限的工具
        - OR 用户有按标签使用权限的工具
        - OR 用户有按标签管理权限的工具
        """
        return (
            self.local_tool_filter
            | self.get_tool_filter_by_tool_action(action=ActionEnum.USE_TOOL)
            | self.get_tool_filter_by_tool_action(action=ActionEnum.MANAGE_TOOL)
            | self.get_tool_filter_by_tag_action(action=ActionEnum.USE_TOOL_BY_TAG)
            | self.get_tool_filter_by_tag_action(action=ActionEnum.MANAGE_TOOL_BY_TAG)
        )


class ToolActionPermission(InstanceActionPermission):
    """
    【通用基类】用于处理工具相关操作的权限校验。
    子类必须定义 `tool_action` 和 `tag_action`。
    """

    # 子类需要覆盖这两个属性
    tool_action: ActionMeta = None
    tag_action: ActionMeta = None

    def __init__(self, *args, **kwargs):
        # 使用子类定义的 action 初始化父类
        if not self.tool_action or not self.tag_action:
            raise NotImplementedError("Subclasses must define 'tool_action' and 'tag_action'.")
        super().__init__(actions=[self.tool_action], resource_meta=ResourceEnum.TOOL, *args, **kwargs)

    def has_permission(self, request, view) -> bool:
        """
        统一的权限校验逻辑：
        1. 用户是工具的创建者。
        2. 用户拥有工具所关联标签的相应权限。
        3. 用户拥有直接操作工具的权限（由父类处理）。
        """
        tool_uid = self._get_instance_id(request, view)
        tool = Tool.last_version_tool(uid=tool_uid)
        if not tool:
            raise ToolDoesNotExist()

        username = get_request_username()

        # 1. 如果是自己的工具，则直接拥有权限
        if tool.is_created_by(username):
            return True

        # 2. 如果工具有标签，则检查标签权限
        tool_tag_ids: Set[int] = set(tool.get_tags().values_list("tag_id", flat=True))
        if tool_tag_ids:
            tool_permission = ToolPermission(username=username)
            # 使用子类定义的 tag_action 进行校验
            auth_tool_tag_ids: Set[int] = set(
                tool_permission.fetch_auth_tool_tags(self.tag_action).values_list("tag_id", flat=True)
            )
            # 如果用户有权限的标签与工具的标签有交集，则有权限
            if auth_tool_tag_ids & tool_tag_ids:
                return True

        # 3. 回退到父类，检查用户是否拥有直接操作工具实例的权限
        return super().has_permission(request, view)


class UseToolPermission(ToolActionPermission):
    """
    检查用户是否拥有使用工具的权限。
    """

    tool_action = ActionEnum.USE_TOOL
    tag_action = ActionEnum.USE_TOOL_BY_TAG


class ManageToolPermission(ToolActionPermission):
    """
    检查用户是否拥有管理工具的权限。
    """

    tool_action = ActionEnum.MANAGE_TOOL
    tag_action = ActionEnum.MANAGE_TOOL_BY_TAG


class CallerContextPermission(BasePermission):
    """调用方资源上下文权限：命中且有权限则整体放行"""

    def has_permission(self, request, view):
        username = get_request_username()
        return should_skip_permission_from(request, username)


def check_bkvision_share_permission(user_id, share_uid) -> bool:
    result = api.bk_vision.check_share_auth(
        username=user_id,
        share_uid=share_uid,
    )
    check_result = result.get("check_result")
    if not check_result:
        raise BkVisionSearchPermissionProhibited(user_id, share_uid)
    return True
