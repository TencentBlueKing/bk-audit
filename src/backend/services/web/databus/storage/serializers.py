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
from django.utils.translation import gettext, gettext_lazy
from rest_framework import serializers

from api.bk_log.constants import CLUSTER_NAME_EN_REGEX
from api.bk_log.serializers import (
    SetupSerializer,
    StorageAuthInfoSerializer,
    StorageHotWarmSerializer,
)
from core.exceptions import ValidationError
from core.utils.time import format_date_string
from services.web.databus.constants import DEFAULT_ALLOCATION_MIN_DAYS, ClusterMode
from services.web.databus.models import RedisConfig


class StorageDeleteRequestSerializer(serializers.Serializer):
    cluster_id = serializers.IntegerField(label=gettext_lazy("集群ID"))


class StorageUpdateRequestSerializer(serializers.Serializer):
    namespace = serializers.CharField(label=gettext_lazy("命名空间"), default=settings.DEFAULT_NAMESPACE)
    cluster_id = serializers.IntegerField(label=gettext_lazy("集群ID"))
    cluster_name = serializers.CharField(label=gettext_lazy("集群名称"), required=False)
    domain_name = serializers.CharField(label=gettext_lazy("集群域名"), required=True)
    port = serializers.IntegerField(label=gettext_lazy("端口"), required=True)
    schema = serializers.CharField(label=gettext_lazy("集群协议"), required=True)
    auth_info = StorageAuthInfoSerializer(label=gettext_lazy("凭据信息"), required=True)
    enable_hot_warm = serializers.BooleanField(label=gettext_lazy("是否开启冷热分离"), default=False)
    allocation_min_days = serializers.IntegerField(label=gettext_lazy("冷热数据生效时间"), default=0)
    hot_attr_name = serializers.CharField(label=gettext_lazy("热节点属性名称"), default="", allow_blank=True)
    hot_attr_value = serializers.CharField(label=gettext_lazy("热节点属性值"), default="", allow_blank=True)
    warm_attr_name = serializers.CharField(label=gettext_lazy("冷节点属性名称"), default="", allow_blank=True)
    warm_attr_value = serializers.CharField(label=gettext_lazy("冷节点属性值"), default="", allow_blank=True)
    setup_config = SetupSerializer(label=gettext_lazy("es设置"))
    source_type = serializers.CharField(label=gettext_lazy("来源"))
    admin = serializers.ListField(label=gettext_lazy("负责人"))
    description = serializers.CharField(label=gettext_lazy("集群描述"), allow_blank=False)
    pre_defined = serializers.BooleanField(label=gettext_lazy("是否为预定义集群，如果是则跳过集群创建更新流程，仅更新项目内配置。"), default=False)
    pre_defined_extra_config = serializers.DictField(label=gettext_lazy("预定义集群额外配置"), required=False, default=dict)

    def validate(self, attrs):
        if not attrs["enable_hot_warm"]:
            return attrs
        if not all(
            [attrs["hot_attr_name"], attrs["hot_attr_value"], attrs["warm_attr_name"], attrs["warm_attr_value"]]
        ):
            raise ValidationError(message=gettext("当冷热数据处于开启状态时，冷热节点属性配置不能为空"))
        if attrs["allocation_min_days"] > attrs["setup_config"]["retention_days_default"]:
            raise ValidationError(message=gettext("数据降冷时间应小于数据过期时间"))
        attrs["es_auth_info"] = attrs["auth_info"]
        return attrs


class StorageListRequestSerializer(serializers.Serializer):
    namespace = serializers.CharField(label=gettext_lazy("Namespace"))
    keyword = serializers.CharField(label=gettext_lazy("搜索关键字"), allow_null=True, allow_blank=True, required=False)


class StorageCustomOptionSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField()
    hot_warm_config = StorageHotWarmSerializer()
    source_type = serializers.CharField()
    setup_config = SetupSerializer()
    admin = serializers.ListField(child=serializers.CharField(allow_blank=True))
    description = serializers.CharField()
    option = serializers.JSONField(required=False)
    cluster_namespace = serializers.CharField(required=False)
    bkbase_tags = serializers.ListField(required=False, child=serializers.CharField())
    bkbase_cluster_id = serializers.RegexField(required=False, regex=CLUSTER_NAME_EN_REGEX)
    visible_config = serializers.JSONField()
    allocation_min_days = serializers.IntegerField(required=False, default=DEFAULT_ALLOCATION_MIN_DAYS)


class StorageClusterConfigSerializer(serializers.Serializer):
    cluster_id = serializers.IntegerField()
    cluster_name = serializers.CharField(label=gettext_lazy("集群名称"))
    domain_name = serializers.CharField(label=gettext_lazy("集群域名"))
    port = serializers.IntegerField(label=gettext_lazy("集群端口"))
    schema = serializers.CharField(label=gettext_lazy("集群协议"))
    enable_hot_warm = serializers.BooleanField(label=gettext_lazy("是否开启冷热数据"), default=False)
    custom_option = StorageCustomOptionSerializer(label=gettext_lazy("自定义字段"))
    creator = serializers.CharField(label=gettext_lazy("创建人"))
    create_time = serializers.DateTimeField(label=gettext_lazy("创建时间"))

    def validate_create_time(self, value):
        return format_date_string(value)


class StorageListResponseSerializer(serializers.Serializer):
    cluster_config = StorageClusterConfigSerializer()
    auth_info = StorageAuthInfoSerializer()
    bk_biz_id = serializers.IntegerField()


class RedisConnectionInfoSerializer(serializers.Serializer):
    enable_sentinel = serializers.BooleanField(label=gettext_lazy("哨兵集群"), default=False)
    name_sentinel = serializers.CharField(label=gettext_lazy("哨兵名"), required=False)
    host_sentinel = serializers.CharField(label=gettext_lazy("哨兵HOST"), required=False)
    port_sentinel = serializers.IntegerField(label=gettext_lazy("哨兵端口"), required=False)
    host = serializers.CharField(label=gettext_lazy("HOST"))
    port = serializers.IntegerField(label=gettext_lazy("端口"))
    password = serializers.CharField(label=gettext_lazy("密码"))


class CreateRedisRequestSerializer(serializers.Serializer):
    namespace = serializers.CharField(label=gettext_lazy("命名空间"))
    redis_id = serializers.CharField(label=gettext_lazy("ID"), required=False)
    redis_name_en = serializers.CharField(label=gettext_lazy("集群ID"))
    redis_name = serializers.CharField(label=gettext_lazy("集群名"))
    connection_info = RedisConnectionInfoSerializer(label=gettext_lazy("连接信息"))
    version = serializers.CharField(label=gettext_lazy("版本"))


class CreateRedisResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = RedisConfig
        exclude = ["updated_at", "updated_by", "created_at", "created_by"]


class StorageCreateRequestSerializer(serializers.Serializer):
    namespace = serializers.CharField(label=gettext_lazy("命名空间"))
    cluster_name = serializers.CharField(label=gettext_lazy("集群名称"))
    bkbase_cluster_en_name = serializers.RegexField(label=gettext_lazy("集群英文名称"), regex=CLUSTER_NAME_EN_REGEX)
    domain_name = serializers.CharField(label=gettext_lazy("集群域名"))
    port = serializers.IntegerField(label=gettext_lazy("集群端口"))
    schema = serializers.CharField(label=gettext_lazy("集群协议"))
    source_type = serializers.CharField(label=gettext_lazy("来源"))
    auth_info = StorageAuthInfoSerializer(label=gettext_lazy("凭据信息"))
    enable_hot_warm = serializers.BooleanField(label=gettext_lazy("是否开启冷热分离"), default=False)
    allocation_min_days = serializers.IntegerField(label=gettext_lazy("冷热数据生效时间"), default=0)
    hot_attr_name = serializers.CharField(label=gettext_lazy("热节点属性名称"), default="", allow_blank=True)
    hot_attr_value = serializers.CharField(label=gettext_lazy("热节点属性值"), default="", allow_blank=True)
    warm_attr_name = serializers.CharField(label=gettext_lazy("冷节点属性名称"), default="", allow_blank=True)
    warm_attr_value = serializers.CharField(label=gettext_lazy("冷节点属性值"), default="", allow_blank=True)
    setup_config = SetupSerializer(label=gettext_lazy("es设置"))
    admin = serializers.ListField(label=gettext_lazy("负责人"))
    description = serializers.CharField(label=gettext_lazy("集群描述"), allow_blank=False)
    pre_defined = serializers.BooleanField(
        label=gettext_lazy("是否为预定义集群，如果是则跳过集群创建更新流程。目前仅支持项目初始化时直接传递配置。"), default=False
    )
    pre_defined_extra_config = serializers.DictField(label=gettext_lazy("预定义集群额外配置"), required=False, default=dict)

    def validate(self, attrs):
        if not attrs["enable_hot_warm"]:
            return attrs
        if not all(
            [attrs["hot_attr_name"], attrs["hot_attr_value"], attrs["warm_attr_name"], attrs["warm_attr_value"]]
        ):
            raise ValidationError(message=gettext("当冷热数据处于开启状态时，冷热节点属性配置不能为空"))
        if attrs["allocation_min_days"] > attrs["setup_config"]["retention_days_default"]:
            raise ValidationError(message=gettext("数据降冷时间应小于数据过期时间"))
        return attrs


class StorageActivateRequestSerializer(serializers.Serializer):
    cluster_id = serializers.IntegerField(
        label=gettext_lazy("集群ID"),
    )
    namespace = serializers.CharField(label=gettext_lazy("命名空间"))
    cluster_mode = serializers.ChoiceField(
        label=gettext_lazy("集群模式"), choices=ClusterMode.choices, default=ClusterMode.MAIN
    )
    config = serializers.DictField(label=gettext_lazy("配置信息"), default=dict, required=False, allow_null=True)
