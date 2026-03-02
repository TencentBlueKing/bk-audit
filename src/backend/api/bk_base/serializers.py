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
from django.conf import settings
from django.utils.translation import gettext_lazy
from rest_framework import serializers

from api.bk_base.constants import AuthType


class QuerySyncRequestSerializer(serializers.Serializer):
    """
    同步查询请求序列化
    """

    bk_app_code = serializers.CharField(label=gettext_lazy("App Code"), default=settings.APP_CODE)
    sql = serializers.CharField(label=gettext_lazy("SQL"))
    prefer_storage = serializers.CharField(label=gettext_lazy("Storage"), allow_blank=True, default="")
    bkdata_authentication_method = serializers.ChoiceField(
        label=gettext_lazy("认证方式"), choices=AuthType.choices, default=AuthType.USER
    )
    bkdata_data_token = serializers.CharField(label=gettext_lazy("Token"), required=False)

    def validate(self, attrs):
        if attrs["bkdata_authentication_method"] == AuthType.TOKEN:
            if not attrs.get("bkdata_data_token"):
                attrs["bkdata_data_token"] = settings.BKBASE_DATA_TOKEN
        return attrs


class DataflowBatchStatusListReqSerializer(serializers.Serializer):
    """
    查询离线任务状态列表
    """

    processing_id = serializers.CharField(label=gettext_lazy("RT ID"))
    data_start = serializers.IntegerField(label=gettext_lazy("查询开始时间"))
    data_end = serializers.IntegerField(label=gettext_lazy("查询结束时间"))
    geog_area_code = serializers.CharField(label=gettext_lazy("地域"), default=settings.BKBASE_GEOG_AREA_CODE)
    limit = serializers.IntegerField(label=gettext_lazy("限制条数"), default=100)
    offset = serializers.IntegerField(label=gettext_lazy("偏移量"), default=0)


class UserAuthCheckReqSerializer(serializers.Serializer):
    user_id = serializers.CharField(label=gettext_lazy("用户ID"))
    action_id = serializers.CharField(label=gettext_lazy("动作ID"))
    object_id = serializers.CharField(label=gettext_lazy("对象ID"))


class UserAuthBatchCheckReqSerializer(serializers.Serializer):
    permissions = serializers.ListField(child=UserAuthCheckReqSerializer())


class UserAuthCheckRespSerializer(serializers.Serializer):
    result = serializers.BooleanField(label=gettext_lazy("是否有权限"))
    user_id = serializers.CharField(label=gettext_lazy("用户ID"))
    object_id = serializers.CharField(label=gettext_lazy("对象ID"))
