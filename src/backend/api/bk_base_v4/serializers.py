"""V4 Query请求及结果校验；行内数值保持上游类型。"""
from rest_framework import serializers


class QuerySyncRequestSerializer(serializers.Serializer):
    """只接受用户态查询协议，不接受旧版数据Token。"""

    sql = serializers.CharField()
    prefer_storage = serializers.CharField(required=False, allow_blank=True)
    bkdata_authentication_method = serializers.ChoiceField(choices=["user"], default="user")
    request_timeout = serializers.FloatField(required=False, min_value=0.001, max_value=300, write_only=True)


class QuerySyncResponseSerializer(serializers.Serializer):
    """校验审计当前使用的行式查询结果，未知存储结构明确失败。"""

    list = serializers.ListField(child=serializers.DictField())
    total_records = serializers.IntegerField(required=False)
    select_fields_order = serializers.ListField(child=serializers.CharField(), required=False)
    timetaken = serializers.FloatField(required=False)


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


class DatasetDetailRequestSerializer(serializers.Serializer):
    namespace = serializers.CharField()
    dataset_name = serializers.CharField()
    storage_type = serializers.CharField(required=False)


class DatasetListRequestSerializer(serializers.Serializer):
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
