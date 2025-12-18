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

from bk_resource import resource
from bk_resource.viewsets import ResourceRoute, ResourceViewSet

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import (
    IAMPermission,
    InstanceActionPermission,
    insert_permission_field,
)
from apps.permission.handlers.resource_types import ResourceEnum


class NoticeViewSet(ResourceViewSet):
    """
    Notice Endpoint
    """

    resource_routes = [
        ResourceRoute("GET", resource.notice.get_msg_type, endpoint="msg_type"),
        ResourceRoute("GET", resource.notice.get_notice_common, endpoint="common"),
    ]


class NoticeGroupsViewSet(ResourceViewSet):
    """
    Notice Group
    """

    def get_permissions(self):
        if self.action in ["list", "retrieve", "all"]:
            return [IAMPermission(actions=[ActionEnum.LIST_NOTICE_GROUP])]
        if self.action in ["create"]:
            return [IAMPermission(actions=[ActionEnum.CREATE_NOTICE_GROUP])]
        if self.action in ["update"]:
            return [
                InstanceActionPermission(
                    actions=[ActionEnum.EDIT_NOTICE_GROUP_V2],
                    resource_meta=ResourceEnum.NOTICE_GROUP,
                    lookup_field="pk",
                )
            ]
        if self.action in ["destroy"]:
            return [
                InstanceActionPermission(
                    actions=[ActionEnum.DELETE_NOTICE_GROUP_V2],
                    resource_meta=ResourceEnum.NOTICE_GROUP,
                    lookup_field="pk",
                )
            ]
        return []

    resource_routes = [
        ResourceRoute(
            "GET",
            resource.notice.list_notice_group,
            enable_paginate=True,
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.EDIT_NOTICE_GROUP_V2, ActionEnum.DELETE_NOTICE_GROUP_V2],
                    id_field=lambda item: item["group_id"],
                    data_field=lambda data: data["results"],
                )
            ],
        ),
        ResourceRoute("GET", resource.notice.list_all_notice_group, endpoint="all"),
        ResourceRoute("GET", resource.notice.retrieve_notice_group, pk_field="group_id"),
        ResourceRoute("POST", resource.notice.create_notice_group),
        ResourceRoute("PUT", resource.notice.update_notice_group, pk_field="group_id"),
        ResourceRoute("DELETE", resource.notice.delete_notice_group, pk_field="group_id"),
    ]
