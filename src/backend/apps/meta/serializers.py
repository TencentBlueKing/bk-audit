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

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.fields import empty

from apps.meta.constants import (
    ALLOWED_LIST_USER_FIELDS,
    DEFAULT_DURATION_TIME,
    DEFAULT_ES_SOURCE_TYPE,
    GLOBAL_CONFIG_LEVEL_INSTANCE,
    LIST_USER_FIELDS,
    LIST_USER_PAGE,
    LIST_USER_PAGE_SIZE,
    LIST_USERS_LOOKUP_FIELD,
    RETRIEVE_USER_FIELDS,
    TAG_NAME_REGEXP,
    ConfigLevelChoices,
    OrderTypeChoices,
    SensitiveResourceTypeEnum,
    SpaceType,
    SystemSortFieldEnum,
)
from apps.meta.exceptions import TagNameInValid
from apps.meta.models import SystemSourceTypeEnum  # 替换为你的实际路径
from apps.meta.models import (
    Action,
    DataMap,
    Field,
    GlobalMetaConfig,
    Namespace,
    ResourceType,
    SensitiveObject,
    System,
    SystemRole,
    Tag,
)
from apps.meta.utils.format import format_resource_permission


class SensitiveObjSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensitiveObject
        fields = "__all__"


class NamespaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Namespace
        fields = ["name", "namespace"]


class SystemSerializer(serializers.ModelSerializer):
    class Meta:
        model = System
        exclude = ["auth_token"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if isinstance(data.get("provider_config"), dict):
            data["provider_config"].pop("token", None)
            data["provider_config"].pop("auth", None)
        return data


class SystemListSerializer(SystemSerializer):
    resource_type_count = serializers.IntegerField(label=gettext_lazy("资源类型数量"), required=False)
    action_count = serializers.IntegerField(label=gettext_lazy("操作数量"), required=False)

    class Meta:
        model = System
        exclude = ["auth_token"]


class SystemRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemRole
        fields = ["role", "username", "system_id"]


class SystemListRequestSerializer(serializers.ModelSerializer):
    keyword = serializers.CharField(label=gettext_lazy("搜索关键字"), allow_blank=True, allow_null=True, required=False)
    order_field = serializers.CharField(label=gettext_lazy("排序字段"), required=False, allow_null=True, allow_blank=True)
    order_type = serializers.ChoiceField(
        label=gettext_lazy("排序方式"), required=False, allow_null=True, allow_blank=True, choices=OrderTypeChoices.choices
    )
    system_status = serializers.CharField(
        label=gettext_lazy("系统状态筛选"), required=False, allow_blank=True, allow_null=True
    )
    status = serializers.CharField(label=gettext_lazy("状态筛选"), required=False, allow_blank=True, allow_null=True)
    source_type = serializers.CharField(label=gettext_lazy("来源类型"), required=False, allow_blank=True, allow_null=True)
    audit_status = serializers.CharField(label=gettext_lazy("审计状态"), required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = System
        fields = [
            "namespace",
            "keyword",
            "order_field",
            "order_type",
            "status",
            "source_type",
            "audit_status",
            "system_status",
        ]

    def validate(self, attrs: dict) -> dict:
        order_field = attrs.pop("order_field", "")
        order_type = attrs.pop("order_type", OrderTypeChoices.ASC.value)
        if not order_field:
            return attrs
        attrs["sort"] = [order_field] if order_type == OrderTypeChoices.ASC.value else [f"-{order_field}"]
        return attrs

    def validate_status(self, status: str) -> list:
        return [i for i in status.split(",") if i]

    def validate_system_status(self, system_status: str) -> list:
        return [i for i in system_status.split(",") if i]

    def validate_source_type(self, source_type: str) -> list:
        return [i for i in source_type.split(",") if i]

    def validate_audit_status(self, audit_status: str) -> list:
        return [i for i in audit_status.split(",") if i]


class SystemListAllRequestSerializer(serializers.ModelSerializer):
    action_ids = serializers.CharField(label=gettext_lazy("权限"), allow_blank=True, allow_null=True, required=False)
    audit_status__in = serializers.CharField(
        label=gettext_lazy("审计状态"),
        required=False,
    )
    source_type__in = serializers.CharField(
        label=gettext_lazy("来源类型"),
        required=False,
    )
    with_favorite = serializers.BooleanField(label=gettext_lazy("携带收藏状态"), default=False)
    with_system_status = serializers.BooleanField(label=gettext_lazy("携带系统状态"), default=False)
    sort_keys = serializers.CharField(
        label=_("排序字段组合"),
        required=False,
        default=SystemSortFieldEnum.PERMISSION.value,
        help_text="permission,favorite,audit_status",
    )

    def validate_sort_keys(self, value: str) -> list:
        return [s.strip() for s in value.split(",") if s.strip()]

    def validate_action_ids(self, value: str):
        if not value:
            return []
        return [action for action in value.split(",") if action.strip()]

    class Meta:
        model = System
        fields = [
            "namespace",
            "action_ids",
            "audit_status__in",
            "source_type__in",
            "with_favorite",
            "with_system_status",
            "sort_keys",
        ]


class SystemListAllResponseSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    favorite = serializers.BooleanField(required=False)

    class Meta:
        model = System
        fields = ['id', 'name', 'source_type', 'audit_status', 'favorite', "system_id"]

    def get_id(self, obj) -> str:
        """系统ID"""
        return obj.system_id

    def get_name(self, obj) -> str:
        """系统名称（优先使用中文名称）"""
        return obj.name or obj.name_en


class SystemRoleListRequestSerializer(serializers.ModelSerializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"), required=False)
    role = serializers.CharField(label=gettext_lazy("角色名称"), required=False)

    class Meta:
        model = SystemRole
        fields = ["system_id", "role"]


class SystemInfoResponseSerializer(SystemSerializer):
    resource_type_count = serializers.IntegerField(label=gettext_lazy("资源类型数量"), required=False)
    action_count = serializers.IntegerField(label=gettext_lazy("操作数量"), required=False)
    managers = serializers.ListField(label=gettext_lazy("应用负责人"), required=False)


class ResourceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceType
        fields = [
            "resource_type_id",
            "name",
            "name_en",
            "sensitivity",
            "provider_config",
            "path",
            "version",
            "description",
            "ancestors",
        ]


class ActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Action
        fields = ["action_id", "name", "name_en", "sensitivity", "type", "version", "description", "unique_id"]


class LabelDataSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()

    def to_representation(self, instance):
        if isinstance(instance, list):
            return instance
        return super().to_representation(instance)


class ESSourceTypeSerializer(LabelDataSerializer):
    ...


class StorageDurationTimeSerializer(LabelDataSerializer):
    id = serializers.IntegerField()
    default = serializers.BooleanField()


class AppInfoSerializer(serializers.Serializer):
    app_code = serializers.CharField()


class GetGlobalsResponseSerializer(serializers.Serializer):
    app_info = AppInfoSerializer()
    es_source_type = ESSourceTypeSerializer(many=True, default=DEFAULT_ES_SOURCE_TYPE)
    storage_duration_time = StorageDurationTimeSerializer(many=True, default=DEFAULT_DURATION_TIME)
    custom_config = serializers.JSONField()


class FieldListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Field
        exclude = ["updated_by", "updated_at", "created_by", "created_at"]


class FieldListRequestSerializer(serializers.Serializer):
    is_etl = serializers.BooleanField(default=True)


class GetCustomFieldsRequestSerializer(serializers.Serializer):
    route_path = serializers.CharField()


class UpdateCustomFieldResponseSerializer(GetCustomFieldsRequestSerializer):
    fields = serializers.JSONField()


class GetAppInfoRequestSerializer(serializers.Serializer):
    namespace = serializers.CharField()
    app_code = serializers.CharField(label="app_code")


class GetAppInfoResponseSerializer(serializers.Serializer):
    app_code = serializers.CharField(allow_blank=True)
    app_name = serializers.CharField(allow_blank=True)
    developers = serializers.ListField(allow_null=True)
    status = serializers.BooleanField()
    status_msg = serializers.CharField()
    system_url = serializers.CharField(allow_blank=True)


class GetResourceTypeSchemaRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"), required=False)
    resource_type_id = serializers.CharField(label=gettext_lazy("资源类型ID"), required=False)


class GlobalMetaConfigListSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalMetaConfig
        fields = ["config_level", "instance_key", "config_key", "config_value"]


class GlobalMetaConfigInfoSerializer(serializers.Serializer):
    config_level = serializers.ChoiceField(choices=ConfigLevelChoices.choices)
    instance_key = serializers.CharField(default=GLOBAL_CONFIG_LEVEL_INSTANCE)
    config_key = serializers.CharField()


class GlobalMetaConfigPostSerializer(GlobalMetaConfigInfoSerializer):
    config_value = serializers.JSONField()


class SystemSearchBaseSerialzier(serializers.Serializer):
    namespace = serializers.CharField()
    system_ids = serializers.CharField(label=gettext_lazy("系统ID"), required=False, allow_null=True, allow_blank=True)

    def validate_system_ids(self, value: str):
        return [i for i in value.split(",") if i]


class GetSpacesMineResponseSerializer(serializers.Serializer):
    """获取空间列表响应序列化"""

    id = serializers.CharField(label=gettext_lazy("空间ID"), required=False)
    name = serializers.CharField(label=gettext_lazy("空间名称"), required=False)
    space_type_id = serializers.CharField(label=gettext_lazy("空间类型ID"), default=SpaceType.UNKNOWN.value)
    space_type_name = serializers.CharField(label=gettext_lazy("空间类型名称"), default=SpaceType.UNKNOWN.label)
    permission = serializers.JSONField(label=gettext_lazy("权限信息"), required=False)

    def to_internal_value(self, data):
        data["id"] = data.get("bk_biz_id")
        data["name"] = data.get("project_name") or data.get("space_name")
        if data.get("permission"):
            data["permission"] = format_resource_permission(data["permission"])
        return super().to_internal_value(data)


class ListUsersRequestSerializer(serializers.Serializer):
    page = serializers.IntegerField(label=gettext_lazy("页码"), default=LIST_USER_PAGE)
    page_size = serializers.IntegerField(label=gettext_lazy("单页数量"), default=LIST_USER_PAGE_SIZE)
    fields = serializers.CharField(label=gettext_lazy("返回字段"), default=LIST_USER_FIELDS)
    lookup_field = serializers.CharField(label=gettext_lazy("查找字段"), required=False)
    fuzzy_lookups = serializers.CharField(label=gettext_lazy("模糊查找关键字"), required=False)
    exact_lookups = serializers.CharField(label=gettext_lazy("精准查找关键字"), required=False)

    def validate_fields(self, value: str):
        _fields = value.split(",")
        not_allowed_fields = {field for field in _fields if field and field not in ALLOWED_LIST_USER_FIELDS}
        if not not_allowed_fields:
            return value
        message = gettext("字段不在允许查询的字段列表中 => %(fields)s") % {"fields": ",".join(not_allowed_fields)}
        raise serializers.ValidationError(message)


class ListUsersResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    display_name = serializers.CharField()


class RetrieveUserRequestSerializer(serializers.Serializer):
    id = serializers.CharField(label=gettext_lazy("用户名"))
    lookup_field = serializers.CharField(label=gettext_lazy("查找字段"), default=LIST_USERS_LOOKUP_FIELD)
    fields = serializers.CharField(label=gettext_lazy("返回字段"), default=RETRIEVE_USER_FIELDS)


class RetrieveUserResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(label=gettext_lazy("ID"), default=0, allow_null=True)
    username = serializers.CharField(label=gettext_lazy("用户名"), allow_blank=True)
    status = serializers.CharField(label=gettext_lazy("状态"), default="", allow_blank=True)
    display_name = serializers.CharField(label=gettext_lazy("显示名称"), default="", allow_blank=True)
    staff_status = serializers.CharField(label=gettext_lazy("雇员状态"), default="", allow_blank=True)
    departments = serializers.ListField(
        label=gettext_lazy("部门"), child=serializers.JSONField(), default=list, allow_null=True
    )
    leader = serializers.ListField(
        label=gettext_lazy("上级"), child=serializers.JSONField(), default=list, allow_null=True
    )
    extras = serializers.JSONField(label=gettext_lazy("拓展信息"), default=dict, allow_null=True)


class UploadDataMapFileRequestSerializer(serializers.Serializer):
    """
    上传数据字典文件
    """

    file = serializers.FileField(label=gettext_lazy("文件"))


class UploadDataMapFileResponseSerializer(serializers.ModelSerializer):
    """
    上传数据字典文件
    """

    class Meta:
        model = DataMap
        fields = ["data_field", "data_key", "data_alias"]


class GetSensitiveObjRequestSerializer(serializers.Serializer):
    """
    获取敏感对象
    """

    system_id = serializers.CharField(label=gettext_lazy("系统ID"))
    resource_type = serializers.ChoiceField(label=gettext_lazy("资源类型"), choices=SensitiveResourceTypeEnum.choices)
    resource_id = serializers.CharField(label=gettext_lazy("资源ID"))


class GetSensitiveObjResponseSerializer(serializers.ModelSerializer):
    """
    获取敏感对象
    """

    class Meta:
        model = SensitiveObject
        fields = ["id", "name"]


class SaveTagsRequestSerializer(serializers.Serializer):
    """
    Save Tags
    """

    tag_name = serializers.CharField(label=gettext_lazy("Tag Name"))

    def validate_tag_name(self, tag_name: str) -> str:
        if not TAG_NAME_REGEXP.match(tag_name):
            raise TagNameInValid(message="{} {}".format(TagNameInValid.MESSAGE, tag_name))
        if tag_name.isdigit():
            raise TagNameInValid(message="{}".format(gettext("标签不能使用纯数字，请修改")))
        return tag_name


class SaveTagResponseSerializer(serializers.ModelSerializer):
    """
    Save Tags
    """

    class Meta:
        model = Tag
        fields = ["tag_id", "tag_name"]


class GetAssetPullInfoRequestSerializer(serializers.Serializer):
    """
    拉取资源信息
    """

    system_id = serializers.CharField(label=gettext_lazy("系统ID"))
    resource_type_id = serializers.CharField(label=gettext_lazy("资源类型ID"))


class ListAllTagsRespSerializer(serializers.ModelSerializer):
    """
    List All Tags Response
    """

    tag_id = serializers.CharField(label=gettext_lazy("Tag ID"))

    class Meta:
        model = Tag
        fields = ["tag_id", "tag_name"]


class GetGlobalChoiceResponseSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()


class ChangeSystemDiagnosisPushReqSerializer(serializers.Serializer):
    """
    Change System Diagnosis
    """

    system_id = serializers.CharField(label=gettext_lazy("系统ID"))
    enable = serializers.BooleanField(label=gettext_lazy("是否启用"))


class ChangeSystemDiagnosisPushRespSerializer(serializers.Serializer):
    """
    Change System Diagnosis
    """

    success = serializers.BooleanField(label=gettext_lazy("是否成功"))


class DeleteSystemDiagnosisPushReqSerializer(serializers.Serializer):
    """
    Delete System Diagnosis
    """

    system_id = serializers.CharField(label=gettext_lazy("系统ID"))


class CreateSystemReqSerializer(serializers.Serializer):
    source_type = serializers.ChoiceField(
        label=_("系统来源类型"), choices=SystemSourceTypeEnum.choices, default=SystemSourceTypeEnum.IAM_V3.value
    )
    instance_id = serializers.CharField(
        label=_("系统实例ID"),
        max_length=32,
    )
    namespace = serializers.CharField(label=_("namespace"), max_length=32)
    name = serializers.CharField(label=_("名称"), max_length=64)
    name_en = serializers.CharField(label=_("英文名称"), allow_blank=False, max_length=64, default="")
    clients = serializers.ListField(
        label=_("客户端"),
        child=serializers.CharField(),
        allow_empty=False,
    )
    description = serializers.CharField(
        label=_("应用描述"),
        allow_blank=True,
        default="",
    )
    callback_url = serializers.CharField(label=_("回调地址"), required=True, allow_blank=True, max_length=255)
    managers = serializers.ListField(label=_("系统管理员"), child=serializers.CharField(), allow_empty=True, default=list)


class UpdateSystemReqSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=_("系统ID"), max_length=64)
    namespace = serializers.CharField(label=_("namespace"), max_length=32)
    clients = serializers.ListField(
        label=_("客户端"),
        child=serializers.CharField(),
        allow_empty=False,
        required=False,
    )
    name = serializers.CharField(
        label=_("名称"),
        required=False,
        allow_blank=False,
        max_length=64,
    )
    name_en = serializers.CharField(
        label=_("英文名称"),
        required=False,
        allow_blank=False,
        max_length=64,
    )
    description = serializers.CharField(
        label=_("应用描述"),
        required=False,
        allow_blank=True,
    )
    callback_url = serializers.CharField(
        label=_("回调地址"),
        required=False,
        allow_blank=False,
        max_length=255,
    )
    managers = serializers.ListField(
        label=_("系统管理员"),
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )


class SystemFavoriteReqSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"))
    favorite = serializers.BooleanField(label=gettext_lazy("是否收藏"))


class ActionCreateSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=_("系统ID"), max_length=64)
    action_id = serializers.CharField(label=_("操作ID"), max_length=64)
    name = serializers.CharField(label=_("名称"), max_length=64)
    name_en = serializers.CharField(label=_("英文名称"), max_length=64, allow_blank=False, default="")
    sensitivity = serializers.IntegerField(label=_("敏感等级"), default=0)
    type = serializers.CharField(label=_("操作类型"), max_length=64, allow_blank=True, default=None)
    version = serializers.IntegerField(label=_("版本"), default=0)
    description = serializers.CharField(label=_("描述信息"), allow_blank=True, default="")
    resource_type_ids = serializers.ListField(
        label=_("资源类型ID"),
        child=serializers.CharField(),
        allow_empty=True,
        default=list,
    )


class ActionUpdateSerializer(serializers.Serializer):
    unique_id = serializers.CharField(label=_("唯一标识"), max_length=255)
    name = serializers.CharField(label=_("名称"), max_length=64, required=False, allow_blank=False)
    name_en = serializers.CharField(label=_("英文名称"), max_length=64, allow_blank=False)
    sensitivity = serializers.IntegerField(label=_("敏感等级"), required=False)
    type = serializers.CharField(label=_("操作类型"), max_length=64, required=False, allow_blank=True)
    version = serializers.IntegerField(label=_("版本"), required=False)
    description = serializers.CharField(
        label=_("描述信息"),
        required=False,
        allow_blank=True,
    )
    resource_type_ids = serializers.ListField(
        label=_("资源类型ID"),
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
    )


class BulkActionCreateSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"))
    actions = serializers.ListField(child=ActionCreateSerializer(), allow_empty=False)

    def run_validation(self, data: dict = empty):
        if isinstance(data, dict) and isinstance(data.get("actions"), list):
            for action in data["actions"]:
                action["system_id"] = data.get("system_id")
        return super().run_validation(data)
