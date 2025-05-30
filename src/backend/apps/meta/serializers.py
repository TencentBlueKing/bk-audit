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

from django.utils.translation import gettext, gettext_lazy
from rest_framework import serializers

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
)
from apps.meta.exceptions import TagNameInValid
from apps.meta.models import (
    Action,
    DataMap,
    Field,
    GeneralConfig,
    GeneralConfigScene,
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
        exclude = ["updated_by", "updated_at", "created_by", "created_at", "auth_token"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if isinstance(data["provider_config"], dict):
            data["provider_config"].pop("token", None)
            data["provider_config"].pop("auth", None)
        return data


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
    status = serializers.CharField(label=gettext_lazy("状态筛选"), required=False, allow_blank=True, allow_null=True)
    source_type = serializers.CharField(label=gettext_lazy("来源类型"), required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = System
        fields = ["namespace", "keyword", "order_field", "order_type", "status", "source_type"]

    def validate(self, attrs: dict) -> dict:
        order_field = attrs.pop("order_field", "")
        order_type = attrs.pop("order_type", OrderTypeChoices.ASC.value)
        if not order_field:
            return attrs
        attrs["sort"] = [order_field] if order_type == OrderTypeChoices.ASC.value else [f"-{order_field}"]
        return attrs

    def validate_status(self, status: str) -> list:
        return [i for i in status.split(",") if i]

    def validate_source_type(self, source_type: str) -> list:
        return [i for i in source_type.split(",") if i]


class SystemListAllRequestSerializer(serializers.ModelSerializer):
    action_ids = serializers.CharField(label=gettext_lazy("权限"), allow_blank=True, allow_null=True, required=False)

    def validate_action_ids(self, value: str):
        if not value:
            return []
        return [action for action in value.split(",") if action.strip()]

    class Meta:
        model = System
        fields = ["namespace", "action_ids"]


class SystemListAllResponseSerializer(serializers.Serializer):
    def to_representation(self, instance: System):
        return {"id": instance.system_id, "name": instance.name or instance.name_en}


class SystemRoleListRequestSerializer(serializers.ModelSerializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"), required=False)
    role = serializers.CharField(label=gettext_lazy("角色名称"), required=False)

    class Meta:
        model = SystemRole
        fields = ["system_id", "role"]


class SystemInfoResponseSerializer(SystemSerializer):
    managers = serializers.ListField(label=gettext_lazy("应用负责人"), required=False)


class ResourceTypeSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField()

    class Meta:
        model = ResourceType
        fields = [
            "unique_id",
            "system_id",
            "resource_type_id",
            "name",
            "name_en",
            "sensitivity",
            "provider_config",
            "path",
            "version",
            "description",
            "ancestor",
            "ancestors",
            'actions',
        ]
        extra_kwargs = {
            "unique_id": {"required": False, "allow_null": True, "allow_blank": True},
        }

        # ---------- 通用校验 / 自动填充 ----------
        def validate(self, attrs):
            """
            统一处理 unique_id：
              • 如果没传，就拼接并写回 attrs
              • 如果传了，必须等于拼接结果
            """
            instance = getattr(self, "instance", None)

            # 先拿到 system_id / resource_type_id（优先新值，其次旧值）
            system_id = attrs.get("system_id") or (instance.system_id if instance else None)
            res_type_id = attrs.get("resource_type_id") or (instance.resource_type_id if instance else None)

            if system_id is None or res_type_id is None:
                raise serializers.ValidationError("system_id 和 resource_type_id 必须同时提供")

            expected = f"{system_id}:{res_type_id}"
            attrs["unique_id"] = expected

            return attrs

    def get_actions(self, obj):
        """
        优化后的方法：优先从 context 中获取预加载的数据。
        """
        # 从 serializer 的 context 中获取预加载的查找字典
        actions_lookup = self.context.get('actions_lookup')

        if actions_lookup is not None:
            # 如果查找字典存在（在 list 视图中），直接从中获取数据，避免查询数据库
            key = (obj.system_id, obj.resource_type_id)
            related_actions = actions_lookup.get(key, [])
        else:
            related_actions = Action.objects.filter(
                system_id=obj.system_id, resource_type_ids__contains=obj.resource_type_id
            )

        return ActionSerializer(related_actions, many=True).data


class ResourceTypeTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = ResourceType
        fields = ('system_id', 'resource_type_id', 'unique_id', 'name', 'name_en', 'description', 'children')

    def get_children(self, obj: ResourceType):
        try:
            child_nodes = obj.tree_node.get_children().select_related("related")
            child_resource_types = [child.related for child in child_nodes]
            serializer = self.__class__(child_resource_types, many=True, context=self.context)
            return serializer.data
        except ResourceType.tree_node.RelatedObjectDoesNotExist:
            return []


class ResourceTypeTreeReqSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"), required=True)


class ListResourceTypeSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"), required=True)
    name = serializers.CharField(label=gettext_lazy("资源类型名称"), required=False)
    name_en = serializers.CharField(label=gettext_lazy("资源类型英文名称"), required=False)


class DeleteResourceTypeRequestSerializer(serializers.Serializer):
    unique_id = serializers.CharField(label=gettext_lazy("unique_id"))


class GetResourceTypeRequestSerializer(serializers.Serializer):
    unique_id = serializers.CharField(label=gettext_lazy("unique_id"))


class ActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Action
        fields = ["action_id", "name", "name_en", "sensitivity", "type", "version", "description"]


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


class GeneralConfigSerializer(serializers.ModelSerializer):
    """Serializer for GeneralConfig"""

    class Meta:
        model = GeneralConfig
        fields = [
            'id',
            'scene',
            'config_name',
            'config_content',
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]


class UpdateGeneralConfigSerializer(GeneralConfigSerializer):
    """Update General Config Request"""

    id = serializers.IntegerField(label=gettext_lazy("配置ID"))


class DeleteGeneralConfigReqSerializer(serializers.Serializer):
    """Delete General Config Request"""

    id = serializers.IntegerField(label=gettext_lazy("配置ID"))


class ListGeneralConfigReqSerializer(serializers.Serializer):
    """List General Config Response"""

    scene = serializers.ChoiceField(choices=GeneralConfigScene.choices, required=False)
    config_name = serializers.CharField(max_length=255, required=False)
    created_by = serializers.CharField(max_length=255)
