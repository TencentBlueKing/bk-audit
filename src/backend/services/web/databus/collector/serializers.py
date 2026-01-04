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

from django.conf import settings
from django.utils.translation import gettext, gettext_lazy
from rest_framework import serializers

from api.bk_log.serializers import CollectorEtlParamsSerializer
from apps.exceptions import ParamsNotValid
from apps.meta.models import Field
from apps.meta.utils.fields import STANDARD_FIELDS
from core.exceptions import ValidationError
from services.web.databus import models
from services.web.databus.collector_plugin.serializers import PluginParamSerializer
from services.web.databus.constants import (
    COLLECTOR_CONFIG_NAME_EN_REGEX,
    COLLECTOR_CONFIG_NAME_REGEX,
    DEFAULT_TARGET_OBJECT_TYPE,
    ContainerCollectorType,
    EtlConfigEnum,
    JoinDataPullType,
    JoinDataType,
    LogReportStatus,
    RecordLogTypeChoices,
    SelectSdkTypeChoices,
    SnapShotStorageChoices,
    TargetNodeTypeChoices,
)
from services.web.databus.models import (
    CollectorConfig,
    Snapshot,
    SnapshotCheckStatistic,
)


class SnapshotStatusRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"), required=True)
    resource_type_ids = serializers.CharField(label=gettext_lazy("资源类型ID"), required=True, allow_blank=True)

    def validate_resource_type_ids(self, value: str) -> list:
        return [resource_tyoe_id for resource_tyoe_id in value.split(",") if resource_tyoe_id]


class TargetNodeSerializer(serializers.Serializer):
    """
    采集目标序列化
    """

    id = serializers.IntegerField(label=gettext_lazy("服务实例id"), required=False)
    bk_inst_id = serializers.IntegerField(label=gettext_lazy("节点实例id"), required=False)
    bk_obj_id = serializers.CharField(label=gettext_lazy("节点对象"), max_length=64, required=False)
    ip = serializers.CharField(label=gettext_lazy("主机实例ip"), max_length=15, required=False)
    bk_cloud_id = serializers.IntegerField(label=gettext_lazy("蓝鲸云区域id"), required=False)
    bk_supplier_id = serializers.CharField(label=gettext_lazy("供应商id"), required=False)


class CollectorCreateRequestSerializer(serializers.Serializer):
    namespace = serializers.CharField()
    system_id = serializers.CharField(label=gettext_lazy("系统ID"))
    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"))
    platform_username = serializers.CharField(label=gettext_lazy("数据平台用户"), required=False)
    bkdata_biz_id = serializers.IntegerField(label=gettext_lazy("数据平台业务ID"), required=False)
    collector_config_name = serializers.RegexField(
        label=gettext_lazy("采集名称"), max_length=32, regex=COLLECTOR_CONFIG_NAME_REGEX
    )
    collector_config_name_en = serializers.RegexField(
        label=gettext_lazy("采集英文名称"), min_length=5, max_length=50, regex=COLLECTOR_CONFIG_NAME_EN_REGEX
    )
    target_object_type = serializers.CharField(label=gettext_lazy("目标类型"), default=DEFAULT_TARGET_OBJECT_TYPE)
    target_node_type = serializers.ChoiceField(label=gettext_lazy("节点类型"), choices=TargetNodeTypeChoices.choices)
    target_nodes = TargetNodeSerializer(label=gettext_lazy("目标节点"), many=True)
    data_encoding = serializers.CharField(label=gettext_lazy("日志字符集"))
    params = PluginParamSerializer()

    # 前置：记录日志参数
    record_log_type = serializers.ChoiceField(
        label="日志接入方式", choices=RecordLogTypeChoices, default=RecordLogTypeChoices.SDK
    )
    select_sdk_type = serializers.ChoiceField(
        label="选择SDK", choices=SelectSdkTypeChoices, default=SelectSdkTypeChoices.PYTHON_SDK
    )


class CollectorCreateResponseSerializer(serializers.ModelSerializer):
    task_id_list = serializers.ListField(label=gettext_lazy("任务ID列表"), child=serializers.CharField(), required=False)

    class Meta:
        model = models.CollectorConfig
        exclude = ["updated_at", "updated_by", "created_at", "created_by", "is_deleted"]


class GetCollectorsRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"))


class GetCollectorsResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CollectorConfig
        exclude = ["id", "updated_at", "updated_by", "created_at", "created_by", "is_deleted", "fields"]


class GetCollectorInfoResponseSerializer(GetCollectorsResponseSerializer):
    class Meta:
        model = models.CollectorConfig
        exclude = ["id", "updated_at", "updated_by", "created_at", "created_by", "is_deleted"]


class CollectorStatusRequestSerializer(serializers.Serializer):
    namespace = serializers.CharField(label=gettext_lazy("命名空间"))
    system_id = serializers.CharField(label=gettext_lazy("系统ID"))


class CollectorStatusSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"))
    status = serializers.ChoiceField(label=gettext_lazy("状态"), choices=LogReportStatus.choices)
    status_msg = serializers.CharField(label=gettext_lazy("状态描述"))
    last_time = serializers.DateTimeField(label=gettext_lazy("最后数据上报时间"), allow_null=True)
    collector_count = serializers.IntegerField(label=gettext_lazy("采集项数量"))


class CollectorStatusResponseSerializer(CollectorStatusSerializer):
    ...


class BulkSystemCollectorsStatusRequestSerializer(serializers.Serializer):
    namespace = serializers.CharField(label=gettext_lazy("命名空间"))
    system_ids = serializers.CharField(label=gettext_lazy("系统ID"))

    def validate_system_ids(self, value: str):
        if not value:
            return []
        return [system_id for system_id in value.split(",") if system_id]


class BulkSystemSnapshotsStatusRequestSerializer(serializers.Serializer):
    system_ids = serializers.CharField(label=gettext_lazy("系统ID"))

    def validate_system_ids(self, value: str):
        if not value:
            return []
        return [system_id for system_id in value.split(",") if system_id]


class BulkSystemCollectorsStatusResponseSerializer(serializers.Serializer):
    system_id0 = CollectorStatusSerializer()
    system_id1 = CollectorStatusSerializer()


class UpdateCollectorRequestSerializer(serializers.Serializer):
    platform_username = serializers.CharField(label=gettext_lazy("数据平台用户"), required=False)
    collector_config_id = serializers.IntegerField(label=gettext_lazy("采集项ID"))
    collector_config_name = serializers.RegexField(
        label=gettext_lazy("采集名称"), max_length=32, regex=COLLECTOR_CONFIG_NAME_REGEX
    )
    collector_config_name_en = serializers.RegexField(
        label=gettext_lazy("采集英文名称"), min_length=5, max_length=50, regex=COLLECTOR_CONFIG_NAME_EN_REGEX
    )
    target_object_type = serializers.CharField(label=gettext_lazy("目标类型"), default=DEFAULT_TARGET_OBJECT_TYPE)
    target_node_type = serializers.CharField(label=gettext_lazy("节点类型"))
    target_nodes = TargetNodeSerializer(label=gettext_lazy("目标节点"), many=True)
    data_encoding = serializers.CharField(label=gettext_lazy("日志字符集"))
    description = serializers.CharField(
        label=gettext_lazy("备注说明"), max_length=64, required=False, allow_null=True, allow_blank=True
    )
    params = PluginParamSerializer()

    # 前置：记录日志参数
    record_log_type = serializers.ChoiceField(
        label="日志接入方式", choices=RecordLogTypeChoices, default=RecordLogTypeChoices.SDK
    )
    select_sdk_type = serializers.ChoiceField(
        label="选择SDK", choices=SelectSdkTypeChoices, default=SelectSdkTypeChoices.PYTHON_SDK
    )


class CollectorEtlFieldsSerializer(serializers.ModelSerializer):
    field_name = serializers.CharField()

    class Meta:
        model = Field
        fields = "__all__"

    def validate(self, attrs):
        if attrs["is_required"] and not attrs["option"]:
            raise serializers.ValidationError("{} => {}".format(gettext("必须字段未传入映射值"), attrs["field_name"]))
        return attrs


class CreateCollectorEtlRequestSerializer(serializers.Serializer):
    namespace = serializers.CharField()
    collector_config_id = serializers.IntegerField(label=gettext_lazy("采集插件ID"))
    etl_config = serializers.ChoiceField(label=gettext_lazy("清洗配置"), choices=EtlConfigEnum.choices)
    etl_params = CollectorEtlParamsSerializer(label=gettext_lazy("清洗参数"))
    fields = CollectorEtlFieldsSerializer(label=gettext_lazy("字段列表"), many=True)

    def validate(self, attrs):
        attrs["fields"] = [field for field in attrs["fields"] if field.get("option", {}).get("path")]
        etl_fields = {field["field_name"] for field in attrs["fields"]}
        required_fields = {field.field_name for field in STANDARD_FIELDS if field.is_required and field.is_display}
        unsigned_fields = list(required_fields - etl_fields)
        if unsigned_fields:
            raise ParamsNotValid(message="{} => {}".format(gettext("字段未提供"), ",".join(unsigned_fields)))
        return attrs


class CreateCollectorEtlResponseSerializer(GetCollectorInfoResponseSerializer):
    ...


class EtlPreviewEtlParamSerializer(serializers.Serializer):
    delimiter = serializers.CharField(
        label=gettext_lazy("分隔符"), required=False, allow_blank=True, trim_whitespace=False
    )
    regexp = serializers.CharField(label=gettext_lazy("正则表达式"), required=False, allow_blank=True)


class EtlPreviewRequestSerializer(serializers.Serializer):
    data = serializers.CharField(label=gettext_lazy("原始日志"))
    etl_config = serializers.ChoiceField(label=gettext_lazy("清洗配置"), choices=EtlConfigEnum.choices)
    etl_params = EtlPreviewEtlParamSerializer(required=False)

    def validate(self, attrs):
        etl_config = attrs["etl_config"]
        if etl_config == EtlConfigEnum.BK_LOG_DELIMITER.value and "delimiter" not in attrs.get("etl_params", {}).keys():
            raise serializers.ValidationError(gettext("分隔符不能为空"))
        if etl_config == EtlConfigEnum.BK_LOG_REGEXP.value and "regexp" not in attrs.get("etl_params", {}).keys():
            raise serializers.ValidationError(gettext("正则表达式不能为空"))
        return attrs


class ListJoinDataRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"))


class ToggleJoinDataRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"))
    resource_type_id = serializers.CharField(label=gettext_lazy("资源类型ID"))
    is_enabled = serializers.BooleanField(label=gettext_lazy("启用数据关联"))
    pull_type = serializers.ChoiceField(
        label=gettext_lazy("拉取类型"),
        choices=JoinDataPullType.choices,
        default=JoinDataPullType.PARTIAL,
    )
    storage_type = serializers.MultipleChoiceField(
        choices=SnapShotStorageChoices.choices,
        label=gettext_lazy("存储类型"),
        default=[SnapShotStorageChoices.HDFS.value, SnapShotStorageChoices.DORIS.value],
    )
    join_data_type = serializers.ChoiceField(
        label=gettext_lazy("关联数据类型"), choices=JoinDataType.choices, default=JoinDataType.ASSET.value
    )
    custom_config = serializers.JSONField(label=gettext_lazy("自定义配置"), required=False, allow_null=True)


class ToggleJoinDataResponseSerializer(serializers.ModelSerializer):
    storage_type = serializers.SerializerMethodField()

    class Meta:
        model = Snapshot
        fields = ["system_id", "resource_type_id", "status", "storage_type", "join_data_type", "custom_config"]

    def get_storage_type(self, obj):
        # 获取与 Snapshot 关联的 storage_type（注意使用反向关系 storages）
        storage_types = obj.storages.all()
        return [storage.storage_type for storage in storage_types]


class GetBcsYamlTemplateRequestSerializer(serializers.Serializer):
    log_config_type = serializers.ChoiceField(label=gettext_lazy("日志类型"), choices=ContainerCollectorType.choices)


class GetBcsYamlTemplateResponseSerializer(serializers.Serializer):
    yaml_config = serializers.CharField()


class BcsCollectorBaseSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"))
    namespace = serializers.CharField(label=gettext_lazy("命名空间"))
    system_id = serializers.CharField(label=gettext_lazy("系统ID"))
    collector_config_name = serializers.RegexField(
        label=gettext_lazy("采集名称"), max_length=32, regex=COLLECTOR_CONFIG_NAME_REGEX
    )
    collector_config_name_en = serializers.RegexField(
        label=gettext_lazy("采集英文名称"), min_length=5, max_length=50, regex=COLLECTOR_CONFIG_NAME_EN_REGEX
    )
    bcs_cluster_id = serializers.CharField(label=gettext_lazy("bcs集群id"))
    yaml_config = serializers.CharField(label=gettext_lazy("yaml配置内容"), default="", allow_blank=True)

    # 前置：记录日志参数
    record_log_type = serializers.ChoiceField(
        label="日志接入方式", choices=RecordLogTypeChoices, default=RecordLogTypeChoices.SDK
    )
    select_sdk_type = serializers.ChoiceField(
        label="选择SDK", choices=SelectSdkTypeChoices, default=SelectSdkTypeChoices.PYTHON_SDK
    )

    def validate_yaml_config(self, value):
        try:
            base64.b64decode(value).decode("utf-8")
        except Exception:  # pylint: disable=broad-except
            raise ValidationError(gettext("base64编码解析失败"))
        # 仍然需要返回原来的值用于调用API
        return value


class UpdateBcsCollectorRequestSerializer(BcsCollectorBaseSerializer):
    collector_config_id = serializers.IntegerField(label=gettext_lazy("采集项ID"))


class CreateBcsCollectorRequestSerializer(BcsCollectorBaseSerializer):
    ...


class CreateApiPushRequestSerializer(serializers.Serializer):
    """
    Create API Push Collector
    """

    namespace = serializers.CharField(label=gettext_lazy("命名空间"))
    system_id = serializers.CharField(label=gettext_lazy("系统ID"))
    custom_collector_config_name = serializers.CharField(label=gettext_lazy("用户自定义名称"), required=False)


class GetApiPushRequestSerializer(serializers.Serializer):
    """
    Get API Push Colellector
    """

    system_id = serializers.CharField(label=gettext_lazy("系统ID"))


class DataIdInfoSerializer(serializers.Serializer):
    """
    Data Id Info
    """

    bk_data_id = serializers.IntegerField(label=gettext_lazy("DataID"))
    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"))
    raw_data_name = serializers.CharField(label=gettext_lazy("数据源名称"))
    raw_data_alias = serializers.CharField(label=gettext_lazy("数据源别名"))
    custom_type = serializers.CharField(label=gettext_lazy("接入场景"), allow_null=True)

    def to_internal_value(self, data: dict) -> dict:
        data["bk_data_id"] = data.pop("id", None)
        data["custom_type"] = data.pop("data_scenario", None)
        return super().to_internal_value(data)


class GetDataIdListRequestSerializer(serializers.Serializer):
    """
    Get DataID List
    """

    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"), required=False, default=settings.DEFAULT_BK_BIZ_ID)


class GetDataIdListResponseSerializer(DataIdInfoSerializer):
    """
    Get DataId List
    """

    is_applied = serializers.BooleanField(label=gettext_lazy("是否已接入"), default=False)


class GetDataIdDetailRequestSerializer(serializers.Serializer):
    """
    Get DataID Detail
    """

    bk_data_id = serializers.IntegerField(label=gettext_lazy("DataID"))


class GetDataIdDetailResponseSerializer(DataIdInfoSerializer):
    """
    Get DataID Detail
    """

    sensitivity = serializers.CharField(label=gettext_lazy("敏感等级"))
    data_encoding = serializers.CharField(label=gettext_lazy("编码"))
    bk_app_code = serializers.CharField(label=gettext_lazy("数据源平台"))
    created_by = serializers.CharField(label=gettext_lazy("创建人"))
    created_at = serializers.DateTimeField(label=gettext_lazy("创建时间"))
    updated_by = serializers.CharField(label=gettext_lazy("更新人"))
    updated_at = serializers.DateTimeField(label=gettext_lazy("更新时间"))
    description = serializers.CharField(label=gettext_lazy("描述"), allow_null=True, allow_blank=True)
    active = serializers.BooleanField(label=gettext_lazy("可用状态"))
    bkbase_url = serializers.CharField(label=gettext_lazy("计算平台访问链接"), allow_null=True, allow_blank=True)


class GetDataIdTailRequestSerializer(serializers.Serializer):
    """
    Get DataID Detail
    """

    bk_data_id = serializers.IntegerField(label=gettext_lazy("DataID"))
    parse_json = serializers.BooleanField(label=gettext_lazy("解析Log"), default=False)


class GetDataIdTailResponseSerializer(serializers.Serializer):
    """
    Get DataID Detail
    """

    topic = serializers.CharField(label=gettext_lazy("主题"), allow_blank=True, allow_null=True, required=False)
    value = serializers.CharField(label=gettext_lazy("最近源数据"), allow_blank=True, allow_null=True, required=False)
    parsed_value = serializers.JSONField(label=gettext_lazy("解析后的最近源数据"), allow_null=True, required=False)


class DataIdEtlPreviewRequestSerializer(serializers.Serializer):
    """
    Get Etl Preview
    """

    data = serializers.CharField(label=gettext_lazy("原始日志"))


class ApplyDataIdSourceRequestSerializer(serializers.Serializer):
    """
    Apply Data ID Source
    """

    namespace = serializers.CharField(label=gettext_lazy("命名空间"))
    bk_data_id = serializers.IntegerField(label=gettext_lazy("DataID"))
    system_id = serializers.CharField(label=gettext_lazy("系统ID"))
    custom_collector_en_name = serializers.CharField(label=gettext_lazy("自定义英文名"), required=False)
    custom_collector_ch_name = serializers.CharField(label=gettext_lazy("自定义中文名"), required=False)


class DataIdEtlStorageRequestSerializer(serializers.Serializer):
    """
    Data ID Etl Storage
    """

    namespace = serializers.CharField(label=gettext_lazy("命名空间"))
    bk_data_id = serializers.IntegerField(label=gettext_lazy("DataID"))
    fields = CollectorEtlFieldsSerializer(label=gettext_lazy("字段列表"), many=True)
    etl_params = serializers.JSONField(label=gettext_lazy("清洗配置"), default=dict)

    def validate(self, attrs):
        attrs["fields"] = [field for field in attrs["fields"] if field.get("option", {}).get("path")]
        etl_fields = {field["field_name"] for field in attrs["fields"]}
        required_fields = {field.field_name for field in STANDARD_FIELDS if field.is_required and field.is_display}
        unsigned_fields = list(required_fields - etl_fields)
        if unsigned_fields:
            raise ParamsNotValid(message="{} => {}".format(gettext("字段未提供"), ",".join(unsigned_fields)))
        return attrs


class GetSystemDataIdListRequestSerializer(serializers.Serializer):
    """
    Get System Data ID List
    """

    system_id = serializers.CharField(label=gettext_lazy("系统ID"))


class GetSystemDataIdListResponseSerializer(serializers.ModelSerializer):
    """
    Get System Data ID List
    """

    class Meta:
        model = CollectorConfig
        fields = "__all__"


class DeleteDataIdRequestSerializer(serializers.Serializer):
    """
    Delete Data ID
    """

    bk_data_id = serializers.IntegerField(label=gettext_lazy("DataID"))


class SnapshotCheckStatisticSerializer(serializers.Serializer):
    """
    Join Data Check Statistic
    """

    class Meta:
        model = SnapshotCheckStatistic
        fields = "__all__"
