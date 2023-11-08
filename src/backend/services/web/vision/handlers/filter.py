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
import uuid
from typing import Dict, List

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from bk_resource.utils.common_utils import ignored
from blueapps.utils.request_provider import get_local_request, get_request_username

from apps.permission.handlers.actions import ActionEnum, get_action_by_id
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import PermissionException
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
    def check_data(self, input_data: str) -> None:
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
        permission = Permission(get_request_username())
        request = permission.make_request(action=get_action_by_id(ActionEnum.VIEW_PANEL), resources=[])
        policies = permission.iam_client._do_policy_query(request)
        if policies:
            result = DeptConvertor().convert(policies)
            authed_dept = authed_dept.union(set(result.value))

        return [{"label": dept, "value": dept, "uuid": uuid.uuid1()} for dept in authed_dept]

    def check_data(self, input_data: str) -> None:
        # 获取有权限的架构
        departments = self.get_data()
        for dept in departments:
            if input_data.startswith(dept["value"]):
                return

        # 无权限申请
        apply_data, apply_url = Permission().get_apply_data(
            [ActionEnum.VIEW_PANEL], [ResourceEnum.DEPT_BK_USERMGR.create_instance(instance_id=input_data)]
        )
        raise PermissionException(
            action_name=str(ActionEnum.VIEW_PANEL.name),
            apply_url=apply_url,
            permission=apply_data,
        )
