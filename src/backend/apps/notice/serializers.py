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

import re

from django.utils.translation import gettext, gettext_lazy
from rest_framework import serializers

from apps.meta.constants import OrderTypeChoices
from apps.notice.constants import NOTICE_GROUP_NAME_REGEX
from apps.notice.exceptions import NoticeGroupNameDuplicate
from apps.notice.models import NoticeGroup


class GetMsgTypeResponseSerializer(serializers.Serializer):
    """
    获取通知类型
    """

    id = serializers.CharField(label=gettext_lazy("ID"))
    name = serializers.CharField(label=gettext_lazy("名称"))
    icon = serializers.CharField(label=gettext_lazy("Icon"))

    class Meta:
        ref_name = "notice.serializers.GetMsgTypeResponseSerializer"

    def to_internal_value(self, data: dict) -> dict:
        return super().to_internal_value({"id": data.get("type"), "name": data.get("label"), "icon": data.get("icon")})


class NoticeGroupInfoSerializer(serializers.ModelSerializer):
    """
    通知组信息
    """

    class Meta:
        model = NoticeGroup
        fields = "__all__"


class ListNoticeGroupRequestSerializer(serializers.Serializer):
    """
    通知组列表
    """

    keyword = serializers.CharField(label=gettext_lazy("关键字"), required=False)
    order_field = serializers.CharField(label=gettext_lazy("排序字段"), required=False)
    order_type = serializers.CharField(label=gettext_lazy("排序方式"), required=False)

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        order_type = data.pop("order_type", None)
        if data.get("order_field") and order_type == OrderTypeChoices.DESC.value:
            data["order_field"] = f"-{data['order_field']}"
        return data


class ListNoticeGroupResponseSerializer(NoticeGroupInfoSerializer):
    """
    通知组列表
    """

    ...


class ListAllNoticeGroupResponseSerializer(serializers.Serializer):
    """
    通知组详情
    """

    id = serializers.IntegerField(label=gettext_lazy("通知组ID"), source="group_id")
    name = serializers.CharField(label=gettext_lazy("通知组名称"), source="group_name")


class RetrieveNoticeGroupRequestSerializer(serializers.Serializer):
    """
    通知组详情
    """

    group_id = serializers.IntegerField(label=gettext_lazy("通知组ID"))


class RetrieveNoticeGroupResponseSerializer(NoticeGroupInfoSerializer):
    """
    通知组详情
    """

    ...


class NoticeConfigSerializer(serializers.Serializer):
    """
    通知配置
    """

    msg_type = serializers.CharField(label=gettext_lazy("通知方式"))


class EditNoticeGroupSerializer(serializers.ModelSerializer):
    """
    创建/编辑通知组
    """

    group_name = serializers.CharField(label=gettext_lazy("通知组名称"))
    group_member = serializers.ListField(
        label=gettext_lazy("通知组成员"), child=serializers.CharField(label=gettext_lazy("RTX"))
    )
    notice_config = NoticeConfigSerializer(label=gettext_lazy("通知配置"), many=True)

    class Meta:
        model = NoticeGroup
        fields = ["group_id", "group_name", "group_member", "notice_config", "description"]

    def validate_group_name(self, group_name: str) -> str:
        match = re.search(NOTICE_GROUP_NAME_REGEX, group_name)
        if match is not None:
            raise serializers.ValidationError(gettext("通知组名称不能包含特殊字符 %s") % match.group())
        return group_name


class CreateNoticeGroupRequestSerializer(EditNoticeGroupSerializer):
    """
    创建通知组
    """

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        if NoticeGroup.objects.filter(group_name=data["group_name"]).exists():
            raise NoticeGroupNameDuplicate()
        return data


class CreateNoticeGroupResponseSerializer(NoticeGroupInfoSerializer):
    """
    创建通知组
    """

    ...


class UpdateNoticeGroupRequestSerializer(EditNoticeGroupSerializer):
    """
    更新通知组
    """

    group_id = serializers.IntegerField(label=gettext_lazy("通知组ID"))

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        if NoticeGroup.objects.filter(group_name=data["group_name"]).exclude(group_id=data["group_id"]).exists():
            raise NoticeGroupNameDuplicate()
        return data


class UpdateNoticeGroupResponseSerializer(NoticeGroupInfoSerializer):
    """
    创建通知组
    """

    ...


class DeleteNoticeGroupRequestSerializer(serializers.Serializer):
    """
    删除通知组
    """

    group_id = serializers.IntegerField(label=gettext_lazy("通知组ID"))

    class Meta:
        ref_name = "notice.serializers.DeleteNoticeGroupRequestSerializer"
