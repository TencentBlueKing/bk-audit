"""V4资源请求及结果校验。"""
from rest_framework import serializers

from api.bk_base_v4.constants import AuthAction


class DirectAuthByResourcesRequestSerializer(serializers.Serializer):
    """按登记归属检查逻辑 RT；七个字段均写入网关请求。"""

    tenant = serializers.CharField(allow_null=True, default=None)
    namespace = serializers.CharField(allow_null=True, default=None)
    user_id = serializers.CharField()
    action_id = serializers.ChoiceField(choices=AuthAction.choices, default=AuthAction.QUERY_DATASET)
    resource_ids = serializers.ListField(child=serializers.CharField())
    parent_resource_type = serializers.CharField(allow_null=True, default=None)
    parent_resource_id = serializers.CharField(allow_null=True, default=None)


class DirectAuthByResourcesResponseSerializer(serializers.BaseSerializer):
    """不转换授权类型；字符串和数字都不能充当 allowed 布尔值。"""

    def to_internal_value(self, data):
        if not isinstance(data, list):
            raise serializers.ValidationError("Expected an authorization result list")
        for row in data:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("resource_id"), str)
                or not row["resource_id"]
                or not isinstance(row.get("allowed"), bool)
            ):
                raise serializers.ValidationError("Invalid authorization result")
        return [{"resource_id": row["resource_id"], "allowed": row["allowed"]} for row in data]

    def to_representation(self, instance):
        return instance


class CleanDebugRequestSerializer(serializers.Serializer):
    """清洗调试输入保留首尾空白，规则使用V4原生配置。"""

    input = serializers.CharField(allow_blank=True, trim_whitespace=False)
    rules = serializers.ListField(child=serializers.DictField())
    filter_rules = serializers.ListField(child=serializers.DictField(), default=list)


class ObjectResponseSerializer(serializers.BaseSerializer):
    """未公布完整模型的对象保持原字段，拒绝非对象返回。"""

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("Expected an object response")
        return data

    def to_representation(self, instance):
        return instance


class ResultTableRequestSerializer(serializers.Serializer):
    result_table_id = serializers.CharField()
    related = serializers.ListField(child=serializers.CharField(), required=False)


class ResultTableInfoRequestSerializer(serializers.Serializer):
    """租户进入请求头，逻辑结果表 ID 仅作为路径参数。"""

    tenant = serializers.CharField()
    result_table_id = serializers.RegexField(r"^[0-9]+_[A-Za-z0-9_]+$")


class BatchStatusListRequestSerializer(serializers.Serializer):
    job_id = serializers.CharField()
    start_time = serializers.CharField()
    end_time = serializers.CharField()
    page_num = serializers.IntegerField(min_value=1)
    page_size = serializers.IntegerField(min_value=1)
    is_data_time = serializers.BooleanField()


class TenantRequestSerializer(serializers.Serializer):
    """正式项目列表仅接受当前企业空间路径参数。"""

    tenant = serializers.CharField()


class DatasetDetailRequestSerializer(serializers.Serializer):
    tenant = serializers.CharField()
    namespace = serializers.CharField()
    dataset_name = serializers.CharField()
    storage_type = serializers.CharField(required=False)


class DatasetListRequestSerializer(serializers.Serializer):
    tenant = serializers.CharField()
    namespace = serializers.CharField()
    page = serializers.IntegerField(default=1, min_value=1)
    page_size = serializers.IntegerField(default=100, min_value=1, max_value=100)
    dataset_name = serializers.CharField(required=False)


class PayloadResponseSerializer(ObjectResponseSerializer):
    """部分MCP及列表API直接返回数组；不猜测未定义包装字段。"""

    def to_internal_value(self, data):
        if not isinstance(data, (dict, list, bool)):
            raise serializers.ValidationError("Unexpected response structure")
        return data


class UserTablesRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.ListField(child=serializers.IntegerField(), required=False)
    need_storage_detail = serializers.IntegerField(default=1)
    result_table_ids = serializers.ListField(child=serializers.CharField(), required=False)


class UserScopesRequestSerializer(serializers.Serializer):
    action_id = serializers.CharField(default="result_table.query_data")
    show_display = serializers.BooleanField(default=True)
    show_admin_scopes = serializers.BooleanField(default=False)
    page = serializers.IntegerField(default=0, min_value=0)


class UserCheckRequestSerializer(serializers.Serializer):
    action_id = serializers.CharField(default="result_table.query_data")
    object_id = serializers.CharField()
    display_detail = serializers.BooleanField(default=False)


class ResourceRefRequestSerializer(serializers.Serializer):
    label_selector = serializers.CharField(required=False)
    tenant = serializers.CharField()
    namespace = serializers.CharField()
    name = serializers.CharField(required=False)


class NamedResourceRequestSerializer(ResourceRefRequestSerializer):
    name = serializers.CharField()


class ResourceWriteRequestSerializer(ResourceRefRequestSerializer):
    metadata = serializers.DictField()
    spec = serializers.DictField()
    status = serializers.JSONField(required=False, allow_null=True, default=None)
    apiVersion = serializers.CharField(required=False)
    kind = serializers.CharField(required=False)


class NamedResourceWriteRequestSerializer(ResourceWriteRequestSerializer):
    name = serializers.CharField()


class RedisAssetConnectionConfigSerializer(serializers.Serializer):
    host = serializers.CharField()
    port = serializers.IntegerField(min_value=1, max_value=65535)
    password = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    db = serializers.IntegerField(required=False, min_value=0)

    def to_internal_value(self, data):
        """原生直连合同不接受被静默丢弃的Sentinel或其他连接选项。"""
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError("Unsupported Redis connection fields")
        return super().to_internal_value(data)


class RedisAssetConnectionSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["Redis"])
    config = RedisAssetConnectionConfigSerializer()


class RedisAssetCreateRequestSerializer(serializers.Serializer):
    tenant = serializers.CharField()
    project_name = serializers.CharField()
    asset_name = serializers.CharField(max_length=64)
    asset_alias = serializers.CharField(max_length=64)
    sub_type = serializers.ChoiceField(choices=["Redis"])
    belong_type = serializers.ChoiceField(choices=["project_private"])
    connection = RedisAssetConnectionSerializer()
    tags = serializers.ListField(child=serializers.CharField(), default=list)
    encrypt_password = serializers.BooleanField(default=True)
    sync_to_iam = serializers.BooleanField(default=True)


class StorageAssetGetRequestSerializer(serializers.Serializer):
    tenant = serializers.CharField()
    project_name = serializers.CharField()
    sub_type = serializers.ChoiceField(choices=["Redis"])
    asset_name = serializers.CharField()


class StorageAssetListRequestSerializer(serializers.Serializer):
    tenant = serializers.CharField()
    project_name = serializers.CharField()
    asset_name = serializers.CharField(required=False)
    asset_type = serializers.ChoiceField(choices=["STORAGE"], default="STORAGE")
    sub_types = serializers.ListField(child=serializers.ChoiceField(choices=["Redis"]), default=lambda: ["Redis"])
    belong_type = serializers.ChoiceField(choices=["project_private", "public", "shared"], required=False)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, default=100)


class NotifyTargetSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=("DataSource", "Flow"))
    namespace = serializers.CharField()
    name = serializers.CharField()


class NotifyGetRequestSerializer(NotifyTargetSerializer):
    tenant = serializers.CharField()


class NotifyUpdateRequestSerializer(serializers.Serializer):
    tenant = serializers.CharField()
    target = NotifyTargetSerializer()
    active = serializers.BooleanField()
    alert_config = serializers.DictField()


class DataIdTailRequestSerializer(serializers.Serializer):
    namespace = serializers.CharField()
    name = serializers.CharField()


class FlowListRequestSerializer(serializers.Serializer):
    project_id = serializers.IntegerField(min_value=1)
    search = serializers.CharField()
    page = serializers.IntegerField(default=1, min_value=1)
    page_size = serializers.IntegerField(default=100, min_value=1)


class FlowIdRequestSerializer(serializers.Serializer):
    flow_id = serializers.IntegerField(min_value=1)
    process_logs = serializers.IntegerField(required=False)


class FlowRestartRequestSerializer(FlowIdRequestSerializer):
    consuming_mode = serializers.ChoiceField(choices=["continue", "from_head", "from_tail"], default="continue")
