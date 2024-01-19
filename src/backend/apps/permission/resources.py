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

from bk_resource import Resource, api
from django.conf import settings
from django.utils.translation import gettext, gettext_lazy

from apps.permission.constants import IAMSystems
from apps.permission.exceptions import GetSystemInfoError
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.auth import AuthHandler
from apps.permission.handlers.permission import Permission
from apps.permission.serializers import (
    BatchIsAllowRequestSerializer,
    CheckPermissionRequestSerializer,
    GetApplyDataRequestSerializer,
)


class IAM:
    tags = ["IAM"]


class SystemResource(IAM, Resource):
    name = gettext_lazy("获取IAM系统配置")

    def perform_request(self, validated_request_data: dict) -> any:
        iam_client = Permission().get_iam_client()
        ok, message, data = iam_client._client.query(settings.BK_IAM_SYSTEM_ID)
        if not ok:
            raise GetSystemInfoError(gettext("获取系统信息错误：%(message)s") % {"message": message})
        return data


class CheckPermissionResource(IAM, Resource):
    name = gettext_lazy("检查当前用户对该动作是否有权限")
    RequestSerializer = CheckPermissionRequestSerializer

    def perform_request(self, validated_request_data: dict) -> any:
        auth_info = AuthHandler.get_auth_info(
            validated_request_data["action_ids"], validated_request_data.get("resources")
        )
        action_ids = [action.get_action_id() for action in auth_info.actions]
        instances = [instance.to_json() for instance in auth_info.instances]

        result = {}
        if auth_info.system_id == settings.BK_IAM_SYSTEM_ID:
            client = Permission()
            resources = client.batch_make_resource(instances)
            for action_id in action_ids:
                result[action_id] = client.is_allowed(action_id, resources)
            return result

        # 日志平台
        return api.bk_log.check_allowed(action_ids=action_ids, resources=instances)


class GetApplyDataResource(IAM, Resource):
    name = gettext_lazy("获取权限申请数据")
    RequestSerializer = GetApplyDataRequestSerializer

    def perform_request(self, validated_request_data: dict) -> any:
        auth_info = AuthHandler.get_auth_info(validated_request_data["action_ids"], validated_request_data["resources"])
        action_ids = [action.get_action_id() for action in auth_info.actions]
        instances = [instance.to_json() for instance in auth_info.instances]

        if auth_info.system_id == settings.BK_IAM_SYSTEM_ID:
            client = Permission()
            resources = client.batch_make_resource(instances)
            apply_data = client.get_apply_data(actions=action_ids, resources=resources)
            return {"permission": apply_data[0], "apply_url": apply_data[1]}

        # 第三方系统目前只支持调用日志平台获取鉴权信息（bk_log_search）
        manage_collection = ActionEnum.MANAGE_COLLECTION_BK_LOG.id.replace(f"_{IAMSystems.BK_LOG.value}", "")
        view_collection = ActionEnum.VIEW_COLLECTION_BK_LOG.id.replace(f"_{IAMSystems.BK_LOG.value}", "")
        if manage_collection in action_ids and view_collection not in action_ids:
            action_ids.append(view_collection)
        data = api.bk_log.get_apply_data(action_ids=action_ids, resources=instances)
        data["permission"] = Permission.translate_apply_data(data["permission"])
        return data


class BatchIsAllowedResource(IAM, Resource):
    name = gettext_lazy("查询某批资源某批操作是否有权限")
    RequestSerializer = BatchIsAllowRequestSerializer

    def perform_request(self, validated_request_data: dict) -> any:
        auth_info = AuthHandler.get_auth_info(
            validated_request_data["action_ids"], validated_request_data.get("resources")
        )
        action_ids = [action.get_action_id() for action in auth_info.actions]

        # 审计中心
        if auth_info.system_id == settings.BK_IAM_SYSTEM_ID:
            # 生成资源实例信息
            resources = []
            instance_ids = {}
            for instance in auth_info.instances:
                if instance.id in instance_ids:
                    continue
                resources.append([auth_info.resource_type_meta.create_simple_instance(instance_id=instance.id)])
                instance_ids[instance.id] = True
            return Permission().batch_is_allowed(auth_info.actions, resources)

        # 日志平台
        bulk_requests = []
        instance_ids = {}
        for instance in auth_info.instances:
            if instance.id in instance_ids:
                continue
            bulk_requests.append({"action_ids": action_ids, "resources": [instance.to_json()]})
            instance_ids[instance.id] = True
        resources = api.bk_log.check_allowed.bulk_request(bulk_requests)

        result = {}
        for index, item in enumerate(bulk_requests):
            instance_id = item["resources"][0]["id"]
            result[instance_id] = resources[index]
        return result
