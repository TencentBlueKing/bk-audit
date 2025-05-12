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

from api.bk_log.constants import (
    DEFAULT_RETENTION,
    DEFAULT_STORAGE_REPLIES,
    EMPTY_PASSWORD_PLACEHOLDER,
    InstanceTypeEnum,
    TemplateTypeChoices,
)
from core.exceptions import ValidationError
from core.utils.time import format_date_string


class StorageAuthInfoSerializer(serializers.Serializer):
    username = serializers.CharField(label=gettext_lazy("用户名"), allow_blank=True)
    password = serializers.CharField(label=gettext_lazy("密码"), allow_blank=True)

    def validate_password(self, value):
        if value == EMPTY_PASSWORD_PLACEHOLDER:
            return ""
        return value


class SetupSerializer(serializers.Serializer):
    retention_days_default = serializers.IntegerField(label=gettext_lazy("默认保留天数"), default=DEFAULT_RETENTION)
    number_of_replicas_default = serializers.IntegerField(label=gettext_lazy("默认副本数"), default=DEFAULT_STORAGE_REPLIES)

    def validate(self, attrs: dict) -> dict:
        attrs["retention_days_max"] = attrs["retention_days_default"]
        attrs["number_of_replicas_max"] = attrs["number_of_replicas_default"]
        return attrs


class StorageHotWarmSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField()
    hot_attr_name = serializers.CharField(default=str, allow_null=True, allow_blank=True)
    hot_attr_value = serializers.CharField(default=str, allow_null=True, allow_blank=True)
    warm_attr_name = serializers.CharField(default=str, allow_null=True, allow_blank=True)
    warm_attr_value = serializers.CharField(default=str, allow_null=True, allow_blank=True)


class StorageDetectRequestSerializer(serializers.Serializer):
    cluster_id = serializers.IntegerField(label=gettext_lazy("集群ID"), required=False)
    domain_name = serializers.CharField(label=gettext_lazy("集群域名"), required=False, allow_blank=True, default="")
    port = serializers.IntegerField(label=gettext_lazy("端口"), allow_null=True, required=False, default=0)
    schema = serializers.CharField(label=gettext_lazy("集群协议"), allow_null=True, required=False, default="")
    version_info = serializers.BooleanField(label=gettext_lazy("是否包含集群信息"), default=False)
    default_auth = serializers.BooleanField(
        label=gettext_lazy("是否使用默认用户信息"), allow_null=True, required=False, default=False
    )
    auth_info = StorageAuthInfoSerializer(label=gettext_lazy("凭据信息"))

    def validate(self, attrs):
        attrs["username"] = attrs["auth_info"].get("username", "")
        attrs["password"] = attrs["auth_info"].get("password", "")
        attrs["es_auth_info"] = attrs["auth_info"]
        return attrs


class StorageBatchConnectivityDetectRequestSerializer(serializers.Serializer):
    cluster_ids = serializers.CharField(label=gettext_lazy("集群ID"))
    origin_resp = serializers.BooleanField(default=False)


class ClusterStatsSerialzier(serializers.Serializer):
    data_node_count = serializers.IntegerField(label=gettext_lazy("数据节点数量"))
    indices_count = serializers.IntegerField(label=gettext_lazy("索引数量"))
    indices_docs_count = serializers.IntegerField(label=gettext_lazy("索引文档数量"))
    indices_store = serializers.IntegerField()
    node_count = serializers.IntegerField(label=gettext_lazy("节点数量"))
    shards_pri = serializers.IntegerField()
    shards_total = serializers.IntegerField(label=gettext_lazy("分片数量"))
    status = serializers.CharField(label=gettext_lazy("节点状态"))
    total_store = serializers.IntegerField()


class StorageBatchConnectivityDetectResponseSerializer(serializers.Serializer):
    cluster_id = serializers.BooleanField(label=gettext_lazy("集群状态"), required=False)


class NodeAttrsResponseSerializer(serializers.Serializer):
    name = serializers.CharField(label=gettext_lazy("节点名"))
    value = serializers.CharField(label=gettext_lazy("节点状态"))
    ip = serializers.CharField(label=gettext_lazy("IP"))
    id = serializers.CharField(label=gettext_lazy("节点ID"))
    host = serializers.CharField(label=gettext_lazy("节点HOST"))
    attr = serializers.CharField(label=gettext_lazy("节点属性"))


class BizsTopoRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"))
    instance_type = serializers.ChoiceField(
        label=gettext_lazy("实例类型"), choices=InstanceTypeEnum.choices, required=False
    )
    remove_empty_nodes = serializers.BooleanField(label=gettext_lazy("是否删除空节点"), required=False)


class BizsTopoSerializer(serializers.Serializer):
    id = serializers.IntegerField(label=gettext_lazy("ID"))
    name = serializers.CharField(label=gettext_lazy("名称"))
    bk_biz_id = serializers.CharField(label=gettext_lazy("业务ID"))
    bk_inst_id = serializers.IntegerField(label=gettext_lazy("实例ID"))
    bk_inst_name = serializers.CharField(label=gettext_lazy("实例名"))
    bk_obj_id = serializers.CharField(label=gettext_lazy("对象ID"))
    bk_obj_name = serializers.CharField(label=gettext_lazy("对象名"))
    default = serializers.IntegerField(label=gettext_lazy("默认"))
    children = serializers.ListField(label=gettext_lazy("子节点"), child=serializers.JSONField())


class BizsTopoResponseSerializer(BizsTopoSerializer):
    children = BizsTopoSerializer(many=True)


class BizsTopoResponseManySerializer(BizsTopoResponseSerializer):
    children = BizsTopoResponseSerializer(many=True)


class SubscriptTaskInstanceStatusSerializer(serializers.Serializer):
    status = serializers.CharField(label=gettext_lazy("运行状态"), allow_null=True, allow_blank=True, required=False)
    ip = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    bk_cloud_id = serializers.IntegerField(label=gettext_lazy("云区域ID"), allow_null=True, required=False)
    log = serializers.CharField(label=gettext_lazy("下发日志"), allow_null=True, allow_blank=True, required=False)
    instance_id = serializers.CharField(label=gettext_lazy("实例ID"), allow_null=True, allow_blank=True, required=False)
    instance_name = serializers.CharField(label=gettext_lazy("节点名称"), allow_null=True, allow_blank=True, required=False)
    task_id = serializers.IntegerField(label=gettext_lazy("任务ID"), allow_null=True, required=False)
    bk_supplier_id = serializers.CharField(
        label=gettext_lazy("云服务商ID"), allow_null=True, allow_blank=True, required=False
    )
    create_time = serializers.CharField(label=gettext_lazy("创建时间"), allow_null=True, allow_blank=True, required=False)
    steps = serializers.JSONField(label=gettext_lazy("步骤"), allow_null=True, required=False)

    def validate_create_time(self, value: str):
        return format_date_string(value)


class SubscriptTaskStatusContentsSerializer(serializers.Serializer):
    is_label = serializers.BooleanField(label=gettext_lazy("是否有标签"), required=False)
    label_name = serializers.CharField(label=gettext_lazy("节点标签"), allow_null=True, allow_blank=True, required=False)
    node_path = serializers.CharField(label=gettext_lazy("节点路径"), allow_null=True, allow_blank=True, required=False)
    bk_inst_id = serializers.CharField(label=gettext_lazy("实例ID"), allow_null=True, allow_blank=True, required=False)
    bk_inst_name = serializers.CharField(label=gettext_lazy("实例名"), allow_null=True, allow_blank=True, required=False)
    bk_obj_id = serializers.CharField(label=gettext_lazy("对象ID"), allow_null=True, allow_blank=True, required=False)
    bk_obj_name = serializers.CharField(label=gettext_lazy("对象名"), allow_null=True, allow_blank=True, required=False)
    child = SubscriptTaskInstanceStatusSerializer(many=True)


class GetSubscriptTaskStatusResponseSerializer(serializers.Serializer):
    contents = SubscriptTaskStatusContentsSerializer(many=True)
    task_ready = serializers.BooleanField(label=gettext_lazy("任务启动状态"), required=False)


class GetSubscriptionStatusResponseSerializer(serializers.Serializer):
    contents = SubscriptTaskStatusContentsSerializer(many=True)


class GetSubscriptTaskStatusRequestSerializer(serializers.Serializer):
    collector_config_id = serializers.IntegerField(label=gettext_lazy("采集项ID"))
    task_id_list = serializers.CharField(label=gettext_lazy("任务ID列表"), allow_blank=True)


class CollectorRequestSerializer(serializers.Serializer):
    collector_config_id = serializers.IntegerField(label=gettext_lazy("采集项ID"))


class CollectorLogItemsSerializer(serializers.Serializer):
    data = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    iterationindex = serializers.IntegerField(required=False, allow_null=True)


class CollectorLogOriginSerializer(serializers.Serializer):
    bizid = serializers.IntegerField(required=False, allow_null=True)
    cloudid = serializers.IntegerField(required=False, allow_null=True)
    dataid = serializers.IntegerField(required=False, allow_null=True)
    datetime = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    ext = serializers.JSONField(required=False, allow_null=True)
    filename = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    gseindex = serializers.IntegerField(required=False, allow_null=True)
    hostname = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    ip = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    items = CollectorLogItemsSerializer(required=False, many=True)
    time = serializers.IntegerField(required=False, allow_null=True)
    utctime = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def validate_datetime(self, value):
        return format_date_string(value)


class CollectorLogEtlSerializer(CollectorLogOriginSerializer):
    data = serializers.CharField()
    log = serializers.CharField()
    iterationindex = serializers.IntegerField()
    batch = serializers.ListField(child=serializers.CharField())


class GetCollectorTailLogResponseSerializer(serializers.Serializer):
    origin = CollectorLogOriginSerializer()


class GetHostInstanceByNodeRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"))
    node_list = BizsTopoSerializer(label=gettext_lazy("节点信息"), many=True)


class BizsTopoSimpleSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"), required=False)
    bk_inst_id = serializers.IntegerField(label=gettext_lazy("实例ID"))
    bk_inst_name = serializers.CharField(label=gettext_lazy("实例名"), required=False)
    bk_obj_id = serializers.CharField(label=gettext_lazy("对象ID"))
    bk_obj_name = serializers.CharField(label=gettext_lazy("对象名"), required=False)


class ListAgentStatusRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"))
    node_list = BizsTopoSimpleSerializer(many=True)


class AgentStatusSerializer(serializers.Serializer):
    node_path = serializers.CharField(label=gettext_lazy("节点路径"))
    labels = serializers.ListField(label=gettext_lazy("标签"), child=serializers.CharField())
    bk_obj_id = serializers.CharField(label=gettext_lazy("对象ID"))
    bk_inst_id = serializers.IntegerField(label=gettext_lazy("实例ID"))
    bk_inst_name = serializers.CharField(label=gettext_lazy("实例名"))
    count = serializers.IntegerField(label=gettext_lazy("Agent数量"))
    agent_error_count = serializers.IntegerField(label=gettext_lazy("Agent错误数量"))


class GetHostInstanceByIPInstanceSerializer(serializers.Serializer):
    ip = serializers.CharField(label=gettext_lazy("IP"))
    bk_cloud_id = serializers.IntegerField(label=gettext_lazy("云区域ID"), required=False, allow_null=True)


class GetHostInstanceByIPRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"))
    ip_list = GetHostInstanceByIPInstanceSerializer(many=True)


class GetHostInstanceByIPResponseSerializer(serializers.Serializer):
    ip = serializers.CharField(label=gettext_lazy("IP"))
    bk_cloud_id = serializers.IntegerField(label=gettext_lazy("云区域ID"))
    bk_cloud_name = serializers.CharField(label=gettext_lazy("云区域名称"))
    agent_status = serializers.CharField(label=gettext_lazy("Agent状态ID"))
    agent_status_name = serializers.CharField(label=gettext_lazy("Agent状态"))
    bk_os_type = serializers.CharField(label=gettext_lazy("操作系统类型"))
    bk_supplier_id = serializers.CharField(label=gettext_lazy("云服务商ID"))
    is_innerip = serializers.BooleanField(label=gettext_lazy("是否内网IP"))


class GetTemplateTopoRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"))
    template_type = serializers.ChoiceField(label=gettext_lazy("模板类型"), choices=TemplateTypeChoices.choices)


class TemplateTopoInstanceSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"))
    bk_obj_id = serializers.CharField(label=gettext_lazy("对象ID"))
    bk_inst_id = serializers.IntegerField(label=gettext_lazy("实例ID"))
    bk_inst_name = serializers.CharField(label=gettext_lazy("实例名"))


class GetTemplateTopoResponseSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"))
    bk_biz_name = serializers.CharField(label=gettext_lazy("业务名称"))
    children = TemplateTopoInstanceSerializer(many=True)


class GetNodesByTemplateRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"))
    bk_inst_ids = serializers.CharField(
        label=gettext_lazy("实例ID"), help_text=gettext_lazy("多个实例以英文逗号分隔"), allow_blank=True
    )
    template_type = serializers.ChoiceField(label=gettext_lazy("模板类型"), choices=TemplateTypeChoices.choices)


class CollectorEtlParamsSerializer(serializers.Serializer):
    delimiter = serializers.CharField(
        label=gettext_lazy("分隔符"), trim_whitespace=False, required=False, allow_null=True, allow_blank=True
    )
    regexp = serializers.CharField(label=gettext_lazy("正则表达式"), required=False, allow_blank=True)
    retain_original_text = serializers.BooleanField(label=gettext_lazy("是否保留原文"), required=False, default=True)


class GetSubscriptTaskDetailRequestSerializer(serializers.Serializer):
    collector_config_id = serializers.IntegerField(label=gettext_lazy("BK-LOG 采集项ID"))
    instance_id = serializers.CharField(label=gettext_lazy("实例ID"))


class RetrySubscriptTaskInstSerializer(serializers.Serializer):
    bk_cloud_id = serializers.IntegerField(label=gettext_lazy("云区域ID"))
    bk_supplier_id = serializers.CharField(label=gettext_lazy("云服务商"))
    ip = serializers.CharField(label=gettext_lazy("IP"))


class RetrySubscriptTaskRequestSerializer(serializers.Serializer):
    collector_config_id = serializers.IntegerField(label=gettext_lazy("BK-LOG 采集项ID"), required=False)
    target_nodes = RetrySubscriptTaskInstSerializer(many=True, required=False)
    instance_id_list = serializers.ListField(
        label=gettext_lazy("实例ID列表(BCS)"), required=False, child=serializers.IntegerField()
    )


class GetEtlPreviewRequestSerializer(serializers.Serializer):
    collector_config_id = serializers.IntegerField(label=gettext_lazy("BK-LOG 采集项ID"))
    etl_config = serializers.CharField(label=gettext_lazy("清洗类型"), required=True)
    etl_params = CollectorEtlParamsSerializer(required=False)
    data = serializers.CharField(label=gettext_lazy("日志内容"), required=True)


class EtlPreviewFieldSerializer(serializers.Serializer):
    field_name = serializers.CharField()
    value = serializers.CharField()


class GetEtlPreviewResponseSerializer(serializers.Serializer):
    fields = EtlPreviewFieldSerializer(many=True)


class GetSubscriptionStatusRequestSerializer(serializers.Serializer):
    collector_config_id = serializers.IntegerField(label=gettext_lazy("BK-LOG 采集项ID"))


class BatchSubscriptionStatusRequestSerializer(serializers.Serializer):
    collector_id_list = serializers.CharField(label=gettext_lazy("BK-LOG 采集项ID"), help_text=gettext_lazy("多个使用英文逗号分隔"))


class BatchSubscriptionStatusResponseSerializer(serializers.Serializer):
    collector_id = serializers.IntegerField(label=gettext_lazy("BK-LOG 采集项ID"))
    subscription_id = serializers.IntegerField(label=gettext_lazy("订阅ID"))
    status = serializers.CharField(label=gettext_lazy("状态"))
    status_name = serializers.CharField(label=gettext_lazy("状态描述"))
    total = serializers.IntegerField(label=gettext_lazy("数量"))
    success = serializers.IntegerField(label=gettext_lazy("成功数量"))
    failed = serializers.IntegerField(label=gettext_lazy("失败数量"))
    pending = serializers.IntegerField(label=gettext_lazy("无结果数量"))


class EsQueryFilterSerializer(serializers.Serializer):
    field = serializers.CharField(label=gettext_lazy("字段名"))
    operator = serializers.CharField(label=gettext_lazy("操作符"))
    value = serializers.ListField(
        label=gettext_lazy("值"), child=serializers.CharField(), allow_null=True, allow_empty=True
    )
    condition = serializers.CharField(label=gettext_lazy("条件"))
    type = serializers.CharField(label=gettext_lazy("类型"))


class GetApplyDataResponseSerializer(serializers.Serializer):
    permission = serializers.JSONField(label=gettext_lazy("权限信息"))
    apply_url = serializers.CharField(label=gettext_lazy("权限URL"))

    def to_internal_value(self, data: dict):
        data["permission"] = data.get("apply_data")
        return super().to_internal_value(data)


class PreCheckCollectorEnNameRequestSerialzier(serializers.Serializer):
    collector_config_name_en = serializers.CharField()
    bk_biz_id = serializers.IntegerField(default=settings.DEFAULT_BK_BIZ_ID)


class PreCheckCollectorEnNameResponseSerialzier(serializers.Serializer):
    allowed = serializers.JSONField()

    def validate(self, attrs):
        return attrs.get("allowed", False)


class ValidateContainerConfigYamlRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"))
    bcs_cluster_id = serializers.CharField(label=gettext_lazy("集群ID"))
    yaml_config = serializers.CharField(label=gettext_lazy("YAML配置的base64"), allow_blank=True)

    def validate_yaml_config(self, value):
        try:
            base64.b64decode(value).decode("utf-8")
        except Exception:  # pylint: disable=broad-except
            raise ValidationError(gettext("base64编码解析失败"))
        # 仍然需要返回原来的值用于调用API
        return value


class ParseResultSerializer(serializers.Serializer):
    start_line_number = serializers.IntegerField()
    end_line_number = serializers.IntegerField()
    message = serializers.CharField()


class ValidateContainerConfigYamlResponseSerializer(serializers.Serializer):
    origin_text = serializers.CharField()
    parse_status = serializers.BooleanField(label=gettext_lazy("校验结果"))
    parse_result = ParseResultSerializer(label=gettext_lazy("校验详情"), many=True)


class ListBcsClustersRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=gettext_lazy("业务ID"))


class ListBcsClustersResponseSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
