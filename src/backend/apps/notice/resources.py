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

from bk_resource import api
from blueapps.utils.request_provider import get_request_username
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy

from apps.audit.resources import AuditMixinResource
from apps.notice.constants import MemberVariable, MsgType
from apps.notice.models import NoticeGroup, NoticeLogV2
from apps.notice.serializers import (
    CreateNoticeGroupRequestSerializer,
    CreateNoticeGroupResponseSerializer,
    DeleteNoticeGroupRequestSerializer,
    GetMsgTypeResponseSerializer,
    GetNoticeCommonResponseSerializer,
    ListAllNoticeGroupResponseSerializer,
    ListNoticeGroupRequestSerializer,
    ListNoticeGroupResponseSerializer,
    NoticeGroupInfoSerializer,
    RetrieveNoticeGroupRequestSerializer,
    RetrieveNoticeGroupResponseSerializer,
    SendNoticeSerializer,
    UpdateNoticeGroupRequestSerializer,
    UpdateNoticeGroupResponseSerializer,
)
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from core.utils.data import choices_to_dict


class NoticeMeta(AuditMixinResource, abc.ABC):
    tags = ["Notice"]
    audit_resource_type = ResourceEnum.NOTICE_GROUP


class GetMsgType(NoticeMeta):
    name = gettext_lazy("消息类型")
    ResponseSerializer = GetMsgTypeResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        local_msg_type = MsgType.values
        cc_msg_type = api.bk_cmsi.get_msg_type()["data"]
        return [
            _msg_type for _msg_type in cc_msg_type if _msg_type["type"] in local_msg_type and _msg_type["is_active"]
        ]


class ListNoticeGroup(NoticeMeta):
    name = gettext_lazy("通知组列表")
    RequestSerializer = ListNoticeGroupRequestSerializer
    ResponseSerializer = ListNoticeGroupResponseSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_NOTICE_GROUP

    def perform_request(self, validated_request_data):
        # 获取所有数据
        notice_groups = NoticeGroup.objects.all()
        # 筛选
        keyword = validated_request_data.get("keyword")
        if keyword:
            q = Q(group_name__icontains=keyword)
            try:
                q |= Q(group_id=int(keyword))
            except ValueError:
                pass
            notice_groups = notice_groups.filter(q)
        # 排序
        order_field = validated_request_data.get("order_field")
        if order_field:
            notice_groups = notice_groups.order_by(order_field)
        # 响应
        return notice_groups


class ListAllNoticeGroup(NoticeMeta):
    name = gettext_lazy("通知组列表(all)")
    ResponseSerializer = ListAllNoticeGroupResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        return NoticeGroup.objects.all()


class RetrieveNoticeGroup(NoticeMeta):
    name = gettext_lazy("通知组详情")
    RequestSerializer = RetrieveNoticeGroupRequestSerializer
    ResponseSerializer = RetrieveNoticeGroupResponseSerializer
    audit_action = ActionEnum.LIST_NOTICE_GROUP

    def perform_request(self, validated_request_data):
        notice_group = get_object_or_404(NoticeGroup, group_id=validated_request_data.pop("group_id"))
        self.add_audit_instance_to_context(instance=notice_group.audit_instance)
        return notice_group


class CreateNoticeGroup(NoticeMeta):
    name = gettext_lazy("创建通知组")
    RequestSerializer = CreateNoticeGroupRequestSerializer
    ResponseSerializer = CreateNoticeGroupResponseSerializer
    audit_action = ActionEnum.CREATE_NOTICE_GROUP

    def perform_request(self, validated_request_data):
        # 存入数据库
        notice_group = NoticeGroup.objects.create(**validated_request_data)
        # 授权
        username = get_request_username()
        if username:
            resource_instance = ResourceEnum.NOTICE_GROUP.create_instance(notice_group.group_id)
            Permission(username).grant_creator_action(resource_instance)
        # 响应
        self.add_audit_instance_to_context(instance=notice_group.audit_instance)
        return notice_group


class UpdateNoticeGroup(NoticeMeta):
    name = gettext_lazy("更新通知组")
    RequestSerializer = UpdateNoticeGroupRequestSerializer
    ResponseSerializer = UpdateNoticeGroupResponseSerializer
    audit_action = ActionEnum.EDIT_NOTICE_GROUP_V2

    def perform_request(self, validated_request_data):
        # 获取实例
        notice_group = get_object_or_404(NoticeGroup, group_id=validated_request_data.pop("group_id"))
        notice_group_origin_data = NoticeGroupInfoSerializer(notice_group).data
        # 更新
        for key, val in validated_request_data.items():
            setattr(notice_group, key, val)
        notice_group.save(update_fields=validated_request_data.keys())
        # 响应
        setattr(notice_group, "instance_origin_data", notice_group_origin_data)
        self.add_audit_instance_to_context(instance=notice_group.audit_instance)
        return notice_group


class DeleteNoticeGroup(NoticeMeta):
    name = gettext_lazy("删除通知组")
    RequestSerializer = DeleteNoticeGroupRequestSerializer
    audit_action = ActionEnum.DELETE_NOTICE_GROUP_V2

    def perform_request(self, validated_request_data):
        # 获取实例
        notice_group = get_object_or_404(NoticeGroup, group_id=validated_request_data.pop("group_id"))
        # 删除
        self.add_audit_instance_to_context(instance=notice_group.audit_instance)
        notice_group.delete()


class SendNotice(NoticeMeta):
    name = gettext_lazy("发送消息")
    RequestSerializer = SendNoticeSerializer

    def perform_request(self, validated_request_data):
        NoticeLogV2.objects.create(**validated_request_data)


class GetNoticeCommon(NoticeMeta):
    name = gettext_lazy("Get Notice Common")
    ResponseSerializer = GetNoticeCommonResponseSerializer

    def perform_request(self, validated_request_data):
        return {
            "member_variable": choices_to_dict(MemberVariable, val="value", name="label"),
        }
