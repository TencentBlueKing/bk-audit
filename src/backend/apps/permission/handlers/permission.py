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
import base64
import os
from typing import Dict, List, Union

from blueapps.utils.logger import logger
from blueapps.utils.request_provider import get_local_request
from django.conf import settings
from django.utils.translation import gettext
from iam import IAM, MultiActionRequest, Request, Resource, Subject
from iam.apply.models import (
    ActionWithoutResources,
    ActionWithResources,
    Application,
    RelatedResourceType,
    ResourceInstance,
    ResourceNode,
)
from iam.auth.models import ApiAuthRequest
from iam.exceptions import AuthAPIError
from iam.meta import setup_action, setup_resource, setup_system
from iam.utils import gen_perms_apply_data
from rest_framework.permissions import BasePermission

from api.domains import BK_IAM_API_URL
from apps.meta.models import GlobalMetaConfig
from apps.permission.constants import FETCH_INSTANCE_TOKEN_KEY
from apps.permission.exceptions import ActionNotExistError, GetSystemInfoError
from apps.permission.handlers.actions import ActionMeta, _all_actions, get_action_by_id
from apps.permission.handlers.resource_types import _all_resources, get_resource_by_id
from core.exceptions import PermissionException


class Permission(object):
    """
    权限中心鉴权封装
    """

    def __init__(self, username: str = "", request=None):
        if username:
            self.username = username
            self.bk_token = ""
        else:
            try:
                request = request or get_local_request()
            except Exception:  # pylint: disable=broad-except
                raise ValueError("must provide `username` or `request` param to init")

            self.bk_token = request.COOKIES.get("bk_token", "")
            self.username = request.user.username

        self.iam_client = self.get_iam_client()

    @classmethod
    def get_iam_client(cls):
        return IAM(settings.APP_CODE, settings.SECRET_KEY, bk_apigateway_url=BK_IAM_API_URL)

    def make_request(self, action: Union[ActionMeta, str], resources: List[Resource] = None) -> Request:
        """
        获取请求对象
        """
        action = get_action_by_id(action)
        resources = resources or []
        request = Request(
            system=settings.BK_IAM_SYSTEM_ID,
            subject=Subject("user", self.username),
            action=action,
            resources=resources,
            environment=None,
        )
        return request

    def make_multi_action_request(
        self, actions: List[Union[ActionMeta, str]], resources: List[Resource] = None
    ) -> MultiActionRequest:
        """
        获取多个动作请求对象
        """
        resources = resources or []
        actions = [get_action_by_id(action) for action in actions]
        request = MultiActionRequest(
            system=settings.BK_IAM_SYSTEM_ID,
            subject=Subject("user", self.username),
            actions=actions,
            resources=resources,
            environment=None,
        )
        return request

    def _make_application(
        self, action_ids: List[str], resources: List[Resource] = None, system_id: str = settings.BK_IAM_SYSTEM_ID
    ) -> Application:

        resources = resources or []
        actions = []

        for action_id in action_ids:
            # 对于没有关联资源的动作，则不传资源
            related_resources_types = []
            try:
                action = get_action_by_id(action_id)
                action_id = action.id
                related_resources_types = action.related_resource_types
            except ActionNotExistError:
                pass

            if not related_resources_types:
                actions.append(ActionWithoutResources(action_id))
            else:
                related_resources = []
                for related_resource in related_resources_types:
                    instances = []
                    for r in resources:
                        resource_nodes = []
                        if r.system == related_resource.system_id and r.type == related_resource.id:
                            if r.attribute.get("_bk_iam_path_"):
                                resource_nodes.extend(
                                    [
                                        ResourceNode(type=_p, id=_id, name=_id)
                                        for _p, _id in [
                                            _p.split(",") for _p in r.attribute["_bk_iam_path_"].strip("/").split("/")
                                        ]
                                    ]
                                )
                            resource_nodes.append(
                                ResourceNode(type=r.type, id=r.id, name=r.attribute.get("name", r.id))
                            )
                            instances.append(ResourceInstance(resource_nodes))

                    related_resources.append(
                        RelatedResourceType(
                            system_id=related_resource.system_id,
                            type=related_resource.id,
                            instances=instances,
                        )
                    )

                actions.append(ActionWithResources(action_id, related_resources))

        application = Application(system_id, actions=actions)
        return application

    def get_apply_url(
        self, action_ids: List[str], resources: List[Resource] = None, system_id: str = settings.BK_IAM_SYSTEM_ID
    ):
        """
        处理无权限 - 跳转申请列表
        """
        application = self._make_application(action_ids, resources, system_id)
        ok, message, url = self.iam_client.get_apply_url(application, self.bk_token, self.username)
        if not ok:
            logger.error(
                "[iam generate apply url fail] "
                "SystemID => %s; "
                "ActionIDs => %s; "
                "Resources => %s; "
                "Message => %s",
                system_id,
                action_ids,
                [resource.to_dict() for resource in resources],
                message,
            )
            return os.getenv("BKPAAS_IAM_URL")
        return url

    def get_apply_data(self, actions: List[Union[ActionMeta, str]], resources: List[Resource] = None):
        """
        生成本系统无权限数据
        """
        resources = resources or []
        action_to_resources_list = []
        for action in actions:
            action = get_action_by_id(action)

            if not action.related_resource_types:
                # 如果没有关联资源，则直接置空
                resources = []

            action_to_resources_list.append({"action": action, "resources_list": [resources]})

        self.setup_meta()

        data = gen_perms_apply_data(
            system=settings.BK_IAM_SYSTEM_ID,
            subject=Subject("user", self.username),
            action_to_resources_list=action_to_resources_list,
        )

        # 国际化
        data = self.translate_apply_data(data=data)

        url = self.get_apply_url(actions, resources)
        return data, url

    @classmethod
    def translate_apply_data(cls, data: dict) -> dict:
        """
        国际化
        """

        if not data:
            return {}

        # 系统名称国际化
        data["system_name"] = gettext(data["system_name"])

        # 逐项国际化
        for _action in data.get("actions", []):
            # 国际化操作名称
            _action["name"] = gettext(_action["name"])
            if "related_resource_types" in _action:
                for _resource in _action["related_resource_types"]:
                    # 国际化资源类型名
                    _resource["type_name"] = gettext(_resource["type_name"])
                    for _instance in _resource["instances"]:
                        for _item in _instance:
                            # 国际化资源类型名
                            _item["type_name"] = gettext(_item["type_name"])
                            # 国际化系统名
                            _item["name"] = gettext(_item["name"])

        return data

    def has_action_any_permission(self, action: Union[ActionMeta, str]) -> bool:
        """
        校验用户是否有动作的任意权限
        :param action: 动作
        """
        action = get_action_by_id(action)
        request = self.make_request(action)

        try:
            # 1. validate
            self.iam_client._validate_request(request)

            # 2. _client.policy_query
            policies = self.iam_client._do_policy_query(request)

            logger.debug("the return policies: %s", policies)
            result = bool(policies)
        except AuthAPIError as e:
            logger.exception(
                "[IAM AuthAPI Error] Action => %s; Err => %s",
                action.to_dict(),
                e,
            )
            result = False

        return result

    def is_allowed(
        self, action: Union[ActionMeta, str], resources: List[Resource] = None, raise_exception: bool = False
    ):
        """
        校验用户是否有动作的权限
        :param action: 动作
        :param resources: 依赖的资源实例列表
        :param raise_exception: 鉴权失败时是否需要抛出异常
        """
        action = get_action_by_id(action)
        if not action.related_resource_types:
            resources = []

        request = self.make_request(action, resources)

        try:
            result = self.iam_client.is_allowed(request)
        except AuthAPIError as e:
            logger.exception(
                "[IAM AuthAPI Error] Action => %s; Resources => %s; Err => %s",
                action.to_dict(),
                [resource.to_dict() for resource in resources],
                e,
            )
            result = False

        if not result and raise_exception:
            apply_data, apply_url = self.get_apply_data([action], resources)
            raise PermissionException(
                action_name=gettext(action.name),
                apply_url=apply_url,
                permission=apply_data,
            )

        return result

    def batch_is_allowed(self, actions: List[ActionMeta], resources: List[List[Resource]]):
        """
        查询某批资源某批操作是否有权限
        """
        request = self.make_multi_action_request(actions)
        result = self.iam_client.batch_resource_multi_actions_allowed(request, resources)
        return result

    @classmethod
    def make_resource(cls, resource_type: str, instance_id: str) -> Resource:
        """
        构造resource对象
        :param resource_type: 资源类型
        :param instance_id: 实例ID
        """
        resource_meta = get_resource_by_id(resource_type)
        return resource_meta.create_instance(instance_id)

    @classmethod
    def batch_make_resource(cls, resources: List[Dict]):
        """
        批量构造resource对象
        """
        return [cls.make_resource(r["type"], r["id"]) for r in resources]

    def get_system_info(self):
        """
        获取权限中心注册的动作列表
        """
        ok, message, data = self.iam_client._client.query(settings.BK_IAM_SYSTEM_ID)
        if not ok:
            raise GetSystemInfoError(gettext("获取系统信息错误：%(message)s") % {"message": message})
        return data

    @classmethod
    def setup_meta(cls):
        """
        初始化权限中心实体
        """
        if getattr(cls, "__setup", False):
            return

        # 系统
        systems = [{"system_id": settings.BK_IAM_SYSTEM_ID, "system_name": settings.BK_IAM_SYSTEM_NAME}]

        for system in systems:
            setup_system(**system)

        # 资源
        for r in _all_resources.values():
            setup_resource(r.system_id, r.id, r.name)

        # 动作
        for action in _all_actions.values():
            setup_action(system_id=settings.BK_IAM_SYSTEM_ID, action_id=action.id, action_name=action.name)

        cls.__setup = True

    def grant_creator_action_attributes(self, resource: Resource, creator: str = None, raise_exception=False):
        """
        新建实例关联权限属性范围授权
        :param resource: 资源实例
        :param creator: 资源创建者
        :param raise_exception: 是否抛出异常
        :return:
        """
        application = {
            "system": resource.system,
            "type": resource.type,
            "creator": creator or self.username,
            "attributes": resource.attribute,
        }

        grant_result = None

        try:
            grant_result = self.iam_client.grant_resource_creator_action_attributes(
                application, self.bk_token, self.username
            )
            logger.info(f"[grant_creator_action] Success! resource: {resource.to_dict()}, result: {grant_result}")
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(f"[grant_creator_action] Failed! resource: {resource.to_dict()}, result: {e}")

            if raise_exception:
                raise e

        return grant_result

    def grant_creator_action(self, resource: Resource, creator: str = None, raise_exception=False):
        """
        新建实例关联权限授权
        :param resource: 资源实例
        :param creator: 资源创建者
        :param raise_exception: 是否抛出异常
        :return:
        """

        application = {
            "system": resource.system,
            "type": resource.type,
            "id": resource.id,
            "name": resource.attribute.get("name", resource.id) if resource.attribute else resource.id,
            "creator": creator or self.username,
        }

        grant_result = None

        try:
            grant_result = self.iam_client.grant_resource_creator_actions(application, self.bk_token, self.username)
            logger.info(f"[grant_creator_action] Success! resource: {resource.to_dict()}, result: {grant_result}")
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(f"[grant_creator_action] Failed! resource: {resource.to_dict()}, result: {e}")

            if raise_exception:
                raise e

        return grant_result

    def grant_instance_permission(self, action: Union[ActionMeta, str], resources: List[Resource] = None):
        """
        主动授权
        """

        request = ApiAuthRequest(
            system=settings.BK_IAM_SYSTEM_ID,
            subject=Subject("user", self.username),
            action=get_action_by_id(action),
            resources=resources,
            environment=None,
            operate="grant",
        )

        self.iam_client.grant_or_revoke_path_permission(
            request=request, bk_token=self.bk_token, bk_username=self.username
        )


class FetchInstancePermission(BasePermission):
    @classmethod
    def build_auth(cls, username, token):
        base64_token = base64.b64encode(f"{username}:{token}".encode("utf-8")).decode("utf-8")
        system_token = f"Basic {base64_token}"
        return system_token

    def has_permission(self, request, view):
        system_token = self.build_auth(settings.FETCH_INSTANCE_USERNAME, GlobalMetaConfig.get(FETCH_INSTANCE_TOKEN_KEY))
        user_auth_token = request.META.get("HTTP_AUTHORIZATION")
        if system_token == user_auth_token:
            return True
        return False
