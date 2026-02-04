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

import abc
from typing import Dict, List, Optional, Union

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from bk_resource.utils.common_utils import ignored
from blueapps.utils.logger import logger
from blueapps.utils.request_provider import get_local_request
from django.db.models import QuerySet
from iam.contrib.converter.queryset import DjangoQuerySetConverter

from apps.meta.models import System, Tag
from apps.permission.handlers.actions import ActionEnum, ActionMeta, get_action_by_id
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import PermissionException
from services.web.vision.exceptions import (
    SingleSystemDiagnosisSystemParamsError,
    VisionPermissionInvalid,
)
from services.web.vision.handlers.convertor import DeptConvertor


class DataFilter(abc.ABC):
    """
    筛选数据处理
    """

    def __init__(self, vision_handler_params: Optional[Dict] = None):
        self.vision_handler_params = vision_handler_params or {}

    @abc.abstractmethod
    def get_data(self) -> List[Dict[str, str]]:
        """
        获取变量数据
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def check_data(self, input_data: Union[List[str], str, int]) -> Union[List[str], str, int]:
        """
        检查数据是否合法及是否有权限
        """

        raise NotImplementedError()

    def get_request_username(self) -> str:
        """
        获取请求的用户身份
        """

        request = get_local_request()
        if not request:
            return ""

        user = getattr(request, "user", None)
        if not user:
            return ""

        return getattr(user, "username", "")


class DeptFilter(DataFilter):
    """
    获取组织架构筛选数据
    """

    def get_data(self) -> List[Dict[str, str]]:
        # 初始化
        authed_dept = set()

        # 获取用户
        username = self.get_request_username()

        # 获取用户组织架构
        with ignored(APIRequestError):
            departments = api.user_manage.list_user_departments(bk_username=username)
            if departments:
                authed_dept.add(departments[0]["full_name"])

        # 获取有权限的组织架构
        permission = Permission(username)
        request = permission.make_request(action=get_action_by_id(ActionEnum.VIEW_PANEL), resources=[])
        policies = permission.iam_client._do_policy_query(request)
        if policies:
            try:
                result = DeptConvertor().convert(policies)
                authed_dept = authed_dept.union(set(result.value))
            except VisionPermissionInvalid as err:
                logger.warning("[%s] %s", str(err), policies)

        data = [{"label": dept, "value": dept} for dept in authed_dept]
        data.sort(key=lambda item: item["label"])
        return data

    def check_data(self, input_data: Union[List[str], str, int]) -> Union[List[str], str, int]:
        # 检查
        is_single = False
        if not isinstance(input_data, list):
            is_single = True
            input_data = [input_data]

        # 获取有权限的架构
        departments = [dept["value"] for dept in self.get_data()]

        # 为空直接范围
        if not input_data and departments:
            return departments

        # 逐个判断权限
        no_permission_dept = []
        for item in input_data:
            has_permission = False
            for dept in departments:
                if item.startswith(dept):
                    has_permission = True
                    break
            if not has_permission:
                no_permission_dept.append(item)

        # 有权限则跳过
        if not no_permission_dept and input_data:
            return input_data[0] if is_single else input_data

        # 无权限申请

        raise PermissionException(
            action_name=str(ActionEnum.VIEW_PANEL.name),
            permission={},  # 传空字典
        )


class TagBasedPermissionFilter(DataFilter):
    @property
    @abc.abstractmethod
    def iam_action(self) -> ActionMeta:
        raise NotImplementedError()

    def get_data(self) -> List[Dict[str, str]]:
        # 初始化
        authed_tag = set()

        # 获取用户
        username = self.get_request_username()

        # 获取有权限的标签
        permission = Permission(username)
        request = permission.make_request(action=get_action_by_id(self.iam_action), resources=[])
        policies = permission.iam_client._do_policy_query(request)
        if policies:
            condition = DjangoQuerySetConverter({"tag.id": "tag_id"}).convert(policies)
            authed_tag = Tag.objects.filter(condition)

        data = [{"label": tag.tag_name, "value": tag.tag_id} for tag in authed_tag]
        data.sort(key=lambda item: item["label"])
        return data

    def check_data(self, input_data: Union[List[str], str, int]) -> Union[List[str], str, int]:
        # 检查
        is_single = False
        if not isinstance(input_data, list):
            input_data = [input_data]
            is_single = True

        # 已授权的标签
        authed_tags = [item["value"] for item in self.get_data()]

        # 为空则直接返回
        if not input_data and authed_tags:
            return authed_tags

        # 检验权限
        Permission(self.get_request_username()).is_allowed(
            action=self.iam_action,
            resources=[ResourceEnum.TAG.create_instance(item) for item in input_data],
            raise_exception=True,
        )

        # 将场景方案的tag_id转换为tag_name返回
        tags = Tag.objects.filter(pk__in=input_data).values("tag_id", "tag_name")
        # 创建tag_id到tag_name的映射
        tag_map = {tag["tag_id"]: tag["tag_name"] for tag in tags}
        # 按输入顺序返回对应的tag_name
        result = [tag_map[tag_id] for tag_id in input_data]
        # 检查通过则返回
        return result[0] if is_single else result


class TagFilter(TagBasedPermissionFilter):
    """
    获取标签数据
    """

    iam_action = ActionEnum.VIEW_TAG_PANEL


class ScenarioViewFilter(TagBasedPermissionFilter):
    """
    获取场景视图权限下可用的标签（Tag）列表
    """

    iam_action = ActionEnum.VIEW_SCENARIO_PANEL


class SystemDiagnosisFilter(DataFilter):
    """
    获取系统诊断面板筛选数据
    权限: 系统诊断面板查看系统权限
    """

    iam_action = ActionEnum.VIEW_SYSTEM_DIAGNOSIS_PANEL

    def _fetch_iam_permissions_systems(self) -> QuerySet[System]:
        """
        获取用户IAM有权限的系统
        """

        # 获取用户
        username = self.get_request_username()
        # 获取有权限的系统
        permission = Permission(username)
        request = permission.make_request(action=get_action_by_id(self.iam_action), resources=[])
        policies = permission.iam_client._do_policy_query(request)
        if policies:
            q = DjangoQuerySetConverter({"system.id": "system_id"}).convert(policies)
            return System.objects.filter(q)
        return System.objects.none()

    def get_data(self, limit_systems: List[str] = None, internal=False) -> List[Dict[str, str]]:
        # 获取有权限的系统
        systems: QuerySet[System] = self._fetch_iam_permissions_systems().distinct().only("system_id", "name")
        data = [
            {"label": system.name, "value": system.system_id}
            for system in systems
            if not limit_systems or system.system_id in limit_systems
        ]
        return sorted(data, key=lambda item: item["label"])

    def check_data(self, input_data: Union[List[str], str, int]) -> Union[List[str], str, int]:
        # 检查
        is_single = False
        if not isinstance(input_data, list):
            input_data = [input_data]
            is_single = True

        # 已授权的标签
        authed_systems = [item["value"] for item in self.get_data(internal=True)]

        # 为空则直接返回
        if not input_data and authed_systems:
            return authed_systems

        # 逐个判断权限
        no_permission_systems = set(input_data) - set(authed_systems)

        # 有权限则跳过
        if not no_permission_systems and input_data:
            return input_data[0] if is_single else input_data

        # 无权限申请
        apply_data, apply_url = Permission().get_apply_data(
            [self.iam_action],
            [ResourceEnum.SYSTEM.create_instance(instance_id=item) for item in no_permission_systems],
        )
        raise PermissionException(
            action_name=str(self.iam_action.name),
            apply_url=apply_url,
            permission=apply_data,
        )


class SingleSystemDiagnosisFilter(SystemDiagnosisFilter):
    """
    获取单个系统诊断面板筛选数据
    权限: 系统编辑权限
    """

    iam_action = ActionEnum.EDIT_SYSTEM

    def get_data(self, limit_systems: List[str] = None, internal=False) -> List[Dict[str, str]]:
        constants = self.vision_handler_params.get("constants", {})
        system_id = constants.get("system_id")
        if internal or system_id and isinstance(system_id, str):
            limit_systems = [] if internal else [system_id]
            return super().get_data(limit_systems=limit_systems)
        raise SingleSystemDiagnosisSystemParamsError()
