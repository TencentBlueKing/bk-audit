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
from typing import Dict, List

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from bk_resource.utils.common_utils import ignored
from blueapps.utils.logger import logger
from blueapps.utils.request_provider import get_local_request
from iam.contrib.converter.queryset import DjangoQuerySetConverter

from apps.meta.models import Tag
from apps.permission.handlers.actions import ActionEnum, get_action_by_id
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import PermissionException
from services.web.vision.exceptions import (
    VisionPermissionInvalid,
    VisionVariableInvalid,
)
from services.web.vision.handlers.convertor import DeptConvertor


class FilterDataHandler:
    """
    筛选数据处理
    """

    @abc.abstractmethod
    def get_data(self) -> List[Dict[str, str]]:
        """
        获取变量数据
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def check_data(self, input_data: List[str]) -> List[str]:
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


class DeptFilterHandler(FilterDataHandler):
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
            departments = api.user_manage.list_user_departments(id=username)
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

    def check_data(self, input_data: List[str]) -> List[str]:
        # 检查
        if not isinstance(input_data, list):
            raise VisionVariableInvalid()

        # 获取有权限的架构
        departments = [dept["value"] for dept in self.get_data()]

        # 为空直接范围
        if not input_data:
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
        if not no_permission_dept:
            return input_data

        # 无权限申请
        apply_data, apply_url = Permission().get_apply_data(
            [ActionEnum.VIEW_PANEL],
            [ResourceEnum.DEPT_BK_USERMGR.create_instance(instance_id=item) for item in no_permission_dept],
        )
        raise PermissionException(
            action_name=str(ActionEnum.VIEW_PANEL.name),
            apply_url=apply_url,
            permission=apply_data,
        )


class TagFilterHandler(FilterDataHandler):
    """
    获取标签数据
    """

    def get_data(self) -> List[Dict[str, str]]:
        # 初始化
        authed_tag = set()

        # 获取用户
        username = self.get_request_username()

        # 获取有权限的标签
        permission = Permission(username)
        request = permission.make_request(action=get_action_by_id(ActionEnum.VIEW_TAG_PANEL), resources=[])
        policies = permission.iam_client._do_policy_query(request)
        if policies:
            condition = DjangoQuerySetConverter().convert(policies)
            authed_tag = Tag.objects.filter(condition)

        data = [{"label": tag.tag_name, "value": tag.tag_id} for tag in authed_tag]
        data.sort(key=lambda item: item["label"])
        return data

    def check_data(self, input_data: List[str]) -> List[str]:
        # 检查
        if not isinstance(input_data, list):
            raise VisionVariableInvalid()

        # 为空则直接返回
        if not input_data:
            return [item["value"] for item in self.get_data()]

        # 检验权限
        Permission(self.get_request_username()).is_allowed(
            action=ActionEnum.VIEW_TAG_PANEL,
            resources=[ResourceEnum.TAG.create_instance(item) for item in input_data],
            raise_exception=True,
        )
