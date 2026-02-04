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
from typing import List

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.fields import empty
from rest_framework.validators import UniqueTogetherValidator

from apps.meta.constants import (
    DEFAULT_DURATION_TIME,
    DEFAULT_ES_SOURCE_TYPE,
    GLOBAL_CONFIG_LEVEL_INSTANCE,
    TAG_NAME_REGEXP,
    ConfigLevelChoices,
    LogReportStatus,
    OrderTypeChoices,
    SensitiveResourceTypeEnum,
    SpaceType,
    SystemAuditStatusEnum,
    SystemPermissionTypeEnum,
    SystemSortFieldEnum,
    SystemStageEnum,
    SystemStatusEnum,
)
from apps.meta.exceptions import TagNameInValid, UniqueNameInValid
from apps.meta.models import (
    Action,
    DataMap,
    EnumMappingRelatedType,
    Field,
    GeneralConfig,
    GeneralConfigScene,
    GlobalMetaConfig,
    Namespace,
    ResourceType,
    ResourceTypeActionRelation,
    SensitiveObject,
    System,
    SystemRole,
    SystemSourceTypeEnum,
    Tag,
)
from apps.meta.utils.format import format_resource_permission
from apps.meta.utils.system import wrapper_system_status
from core.models import get_request_username


class SensitiveObjSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensitiveObject
        fields = "__all__"


class NamespaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Namespace
        fields = ["name", "namespace"]


class SystemSerializer(serializers.ModelSerializer):
    status_msg = serializers.CharField(label=gettext_lazy("状态信息"), required=False)
    status = serializers.ChoiceField(
        label=gettext_lazy("状态"), required=False, allow_null=True, choices=LogReportStatus.choices
    )
    last_time = serializers.CharField(label=gettext_lazy("最后上报时间"), required=False, allow_null=True)
    collector_count = serializers.IntegerField(label=gettext_lazy("采集器数量"), required=False)
    system_status = serializers.ChoiceField(
        label=gettext_lazy("系统状态"),
        required=False,
        choices=SystemStatusEnum.choices,
        allow_null=True,
    )
    system_stage = serializers.ChoiceField(
        label=gettext_lazy("系统阶段"),
        required=False,
        choices=SystemStageEnum.choices,
        allow_null=True,
    )
    system_status_msg = serializers.CharField(
        label=gettext_lazy("系统状态信息"),
        required=False,
        allow_null=True,
    )

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
        label=gettext_lazy("系统状态筛选"),
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text=SystemStatusEnum.choices,
    )
    status = serializers.CharField(label=gettext_lazy("状态筛选"), required=False, allow_blank=True, allow_null=True)
    source_type = serializers.CharField(
        label=gettext_lazy("来源类型"),
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text=SystemSourceTypeEnum.choices,
    )
    audit_status = serializers.CharField(
        label=gettext_lazy("审计状态"),
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text=SystemAuditStatusEnum.choices,
    )

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
    action_ids = serializers.CharField(
        label=gettext_lazy("权限"), allow_blank=True, allow_null=True, required=False, help_text="view_system,edit_system"
    )
    audit_status__in = serializers.CharField(
        label=gettext_lazy("系统审计状态"),
        required=False,
        help_text=SystemAuditStatusEnum.choices,
    )
    source_type__in = serializers.CharField(
        label=gettext_lazy("来源类型"),
        required=False,
        help_text=SystemSourceTypeEnum.choices,
    )
    permission_type__in = serializers.CharField(
        label=gettext_lazy("权限类型"), required=False, help_text=SystemPermissionTypeEnum.choices
    )
    with_favorite = serializers.BooleanField(label=gettext_lazy("携带收藏状态"), default=False)
    with_system_status = serializers.BooleanField(label=gettext_lazy("携带系统状态"), default=False)
    sort_keys = serializers.CharField(
        label=_("排序字段组合"),
        required=False,
        default=SystemSortFieldEnum.PERMISSION.value,
        help_text=SystemSortFieldEnum.choices,
    )
    order_type = serializers.ChoiceField(
        label=gettext_lazy("排序方式"), default=OrderTypeChoices.ASC.value, choices=OrderTypeChoices.choices
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
            "permission_type__in",
            "with_favorite",
            "with_system_status",
            "sort_keys",
            "order_type",
        ]


class SystemListAllResponseSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    favorite = serializers.BooleanField(required=False)

    class Meta:
        model = System
        fields = [
            'id',
            'name',
            "name_en",
            'source_type',
            'audit_status',
            'favorite',
            "system_id",
            "permission_type",
            "instance_id",
        ]

    def get_id(self, obj) -> str:
        """系统ID"""
        return obj.system_id


class SystemRoleListRequestSerializer(serializers.ModelSerializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"), required=False)
    role = serializers.CharField(label=gettext_lazy("角色名称"), required=False)

    class Meta:
        model = SystemRole
        fields = ["system_id", "role"]


class SystemInfoResponseSerializer(SystemSerializer):
    resource_type_count = serializers.IntegerField(label=gettext_lazy("资源类型数量"), required=False)
    action_count = serializers.IntegerField(label=gettext_lazy("操作数量"), required=False)
    managers = serializers.SerializerMethodField(label=gettext_lazy("管理员"), required=False)

    class Meta:
        model = System
        fields = "__all__"

    def get_managers(self, obj: System) -> list:
        """管理员"""
        return obj.managers_list

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # 增加最后上报信息数据
        wrapper_system_status(namespace=data["namespace"], systems=[data])
        return data


class ActionListReqSerializer(serializers.Serializer):
    system_id = serializers.CharField()
    action_id = serializers.CharField(required=False)
    name__icontains = serializers.CharField(required=False)
    name_en__icontains = serializers.CharField(required=False)
    sensitivity = serializers.IntegerField(required=False)
    type = serializers.CharField(required=False)
    resource_type_ids = serializers.CharField(required=False)

    def validate_resource_type_ids(self, value) -> List[str]:
        if not value:
            return []
        return [resource_type_id for resource_type_id in value.split(",") if resource_type_id.strip()]


class ActionSerializer(serializers.ModelSerializer):
    resource_type_ids = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = Action
        fields = [
            "action_id",
            "name",
            "name_en",
            "sensitivity",
            "type",
            "version",
            "description",
            "unique_id",
            "resource_type_ids",
        ]


class ActionCreateSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=_("系统ID"), max_length=64)
    action_id = serializers.CharField(label=_("操作ID"), max_length=64)
    name = serializers.CharField(label=_("名称"), max_length=64)
    name_en = serializers.CharField(label=_("英文名称"), max_length=64, allow_blank=False, required=False)
    sensitivity = serializers.IntegerField(label=_("敏感等级"), default=0)
    type = serializers.CharField(label=_("操作类型"), max_length=64, allow_blank=True, allow_null=True, default=None)
    version = serializers.IntegerField(label=_("版本"), default=0)
    description = serializers.CharField(label=_("描述信息"), allow_blank=True, default="")
    resource_type_ids = serializers.ListField(
        label=_("资源类型ID"),
        child=serializers.CharField(),
        allow_empty=True,
        default=list,
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        attrs["unique_id"] = Action.gen_unique_id(system_id=attrs["system_id"], action_id=attrs["action_id"])
        return attrs


class ResourceTypeSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField(label=gettext_lazy("操作详情"))
    # 支持在创建资源类型时快捷创建操作
    actions_to_create = serializers.ListField(
        child=ActionCreateSerializer(),
        required=False,
        write_only=True,
        help_text=gettext_lazy("操作的 system_id 和 resource_type_ids 会被自动填充"),
    )

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
            "actions",
            "actions_to_create",
        ]
        extra_kwargs = {
            "unique_id": {
                "required": False,
                "allow_null": True,
                "allow_blank": True,
            }
        }

    def run_validation(self, data: dict = empty):
        try:
            # 需要在 run_validation 中默认填充 action 中的 system_id 和 resource_type_ids
            if isinstance(data, dict) and isinstance(data.get("actions_to_create"), list):
                for action in data["actions_to_create"]:
                    action["system_id"] = data.get("system_id")
                    action["resource_type_ids"] = [data.get("resource_type_id")]
            return super().run_validation(data)
        except Exception as e:
            if (
                isinstance(e, serializers.ValidationError)
                and e.detail.get("unique_id")
                and e.detail.get("unique_id")[0].code == "unique"
            ):
                raise UniqueNameInValid(message=gettext_lazy("资源类型已存在"))
            else:
                raise

    # ---------- 通用校验 / 自动填充 ----------
    def validate(self, attrs):
        """
        统一处理 unique_id：默认填充为拼接结果
        """
        instance = getattr(self, "instance", None)

        # 先拿到 system_id / resource_type_id（优先新值，其次旧值）
        system_id = attrs.get("system_id") or (instance.system_id if instance else None)
        res_type_id = attrs.get("resource_type_id") or (instance.resource_type_id if instance else None)

        if not system_id or not res_type_id:
            raise serializers.ValidationError("system_id 和 resource_type_id 必须同时提供")

        expected = f"{system_id}:{res_type_id}"
        if not attrs.get("unique_id"):
            attrs["unique_id"] = expected
        elif attrs["unique_id"] != expected:
            raise serializers.ValidationError("unique_id 必须为 system_id 和 resource_type_id 的组合")

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
                system_id=obj.system_id,
                action_id__in=ResourceTypeActionRelation.objects.filter(
                    system_id=obj.system_id, resource_type_id=obj.resource_type_id
                ).values_list(
                    'action_id', flat=True
                ),  # 使用values_list而不是values
            )
        return ActionSerializer(related_actions, many=True).data


class UpdateResourceTypeSerializer(ResourceTypeSerializer):
    unique_id = serializers.CharField(validators=[])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validators = [
            v
            for v in self.validators
            if not (isinstance(v, UniqueTogetherValidator) and v.fields == ('system_id', 'resource_type_id'))
        ]


class BulkCreateResourceTypeSerializer(serializers.Serializer):
    resource_types = serializers.ListField(child=ResourceTypeSerializer())


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


class ResourceTypeListSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"), required=True)
    name = serializers.CharField(label=gettext_lazy("资源类型名称"), required=False)
    name_en = serializers.CharField(label=gettext_lazy("资源类型英文名称"), required=False)
    sensitivity = serializers.IntegerField(required=False)
    actions = serializers.CharField(required=False, label=gettext_lazy("操作ID列表，多个用逗号分隔"))
    resource_type_id = serializers.CharField(required=False, label=gettext_lazy("资源类型ID"))


class DeleteResourceTypeRequestSerializer(serializers.Serializer):
    unique_id = serializers.CharField(label=gettext_lazy("unique_id"))


class GetResourceTypeRequestSerializer(serializers.Serializer):
    unique_id = serializers.CharField(label=gettext_lazy("unique_id"))


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


class CreateSystemReqSerializer(serializers.ModelSerializer):
    clients = serializers.ListField(
        label=_("客户端"),
        child=serializers.CharField(),
        allow_empty=False,
    )
    managers = serializers.ListField(
        label=_("系统管理员"),
        child=serializers.CharField(),
        allow_empty=True,
    )

    class Meta:
        model = System
        fields = [
            "instance_id",
            "namespace",
            "name",
            "name_en",
            "clients",
            "description",
            "callback_url",
            "system_url",
            "managers",
            "permission_type",
        ]
        extra_kwargs = {
            "instance_id": {
                "required": True,
                "allow_blank": False,
            },
            "name": {
                "required": True,
                "allow_blank": False,
            },
            "name_en": {"allow_blank": True, "default": ""},
            "description": {"allow_blank": True, "default": ""},
            "callback_url": {
                "allow_blank": True,
                "default": "",
            },
        }

    def validate(self, attrs):
        attrs = super().validate(attrs)
        attrs["auth_token"] = System.gen_auth_token()
        attrs["audit_status"] = SystemAuditStatusEnum.ACCESSED.value
        attrs["source_type"] = SystemSourceTypeEnum.AUDIT.value
        attrs["system_id"] = System.build_system_id(source_type=attrs["source_type"], instance_id=attrs["instance_id"])
        # 添加创建者为管理员
        created_by = get_request_username()
        if created_by not in attrs["managers"]:
            attrs["managers"].append(created_by)
        return attrs


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
        allow_blank=True,
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
    system_url = serializers.CharField(
        label=_("系统地址"),
        required=False,
        allow_blank=False,
        max_length=255,
    )
    permission_type = serializers.ChoiceField(
        label=_("权限类型"), choices=SystemPermissionTypeEnum.choices, required=False, allow_null=True, allow_blank=True
    )


class SystemFavoriteReqSerializer(serializers.Serializer):
    system_id = serializers.CharField(label=gettext_lazy("系统ID"))
    favorite = serializers.BooleanField(label=gettext_lazy("是否收藏"))


class ActionUpdateSerializer(serializers.ModelSerializer):
    unique_id = serializers.CharField(label=_("唯一标识"), max_length=255)
    name = serializers.CharField(label=_("名称"), max_length=64, required=False, allow_blank=False)
    name_en = serializers.CharField(label=_("英文名称"), max_length=64, allow_blank=False, required=False)
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

    class Meta:
        model = System
        fields = [
            "unique_id",
            "name",
            "name_en",
            "sensitivity",
            "type",
            "version",
            "description",
            "resource_type_ids",
        ]


class BulkActionCreateSerializer(serializers.Serializer):
    """
    Bulk Create Action
    """

    system_id = serializers.CharField(label=gettext_lazy("系统ID"))
    actions = serializers.ListField(child=ActionCreateSerializer(), allow_empty=False, help_text="操作的系统ID会被自动填充")

    def run_validation(self, data: dict = empty):
        if isinstance(data, dict) and isinstance(data.get("actions"), list):
            for action in data["actions"]:
                action["system_id"] = data.get("system_id")
        return super().run_validation(data)


class EnumMappingRelation(serializers.Serializer):
    related_type = serializers.ChoiceField(required=False, allow_null=True, choices=EnumMappingRelatedType.choices)
    related_object_id = serializers.CharField(max_length=256, required=False, allow_null=True)


class CollectionKeySerializer(serializers.Serializer):
    collection_id = serializers.CharField(max_length=255)
    key = serializers.CharField(max_length=255)


class EnumMappingByCollectionKeysSerializer(EnumMappingRelation, serializers.Serializer):
    collection_keys = serializers.ListField(child=CollectionKeySerializer())


class EnumMappingByCollectionSerializer(EnumMappingRelation, serializers.Serializer):
    collection_id = serializers.CharField(max_length=255)


class EnumMappingSerializer(serializers.Serializer):
    collection_id = serializers.CharField(max_length=255)
    key = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=255)


class InnerEnumMappingSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=255)


class BatchUpdateEnumMappingSerializer(EnumMappingRelation, serializers.Serializer):
    collection_id = serializers.CharField(max_length=255)
    mappings = serializers.ListField(child=InnerEnumMappingSerializer(), allow_empty=True)
