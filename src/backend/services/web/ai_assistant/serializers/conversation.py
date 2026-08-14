from rest_framework import serializers

from services.web.ai_assistant.constants import SidebarNodeType


class ConversationGroupCreateRequestSerializer(serializers.Serializer):
    """创建会话分组，名称入库前统一去除首尾空白。"""

    name = serializers.CharField(
        max_length=64,
        trim_whitespace=True,
        allow_blank=False,
        help_text="会话分组名称，最长 64 个字符",
    )


class ConversationGroupDetailRequestSerializer(serializers.Serializer):
    """通过对外 UUID 定位当前用户的会话分组。"""

    group_uid = serializers.UUIDField(help_text="会话分组对外 UUID")


class ConversationGroupUpdateRequestSerializer(ConversationGroupDetailRequestSerializer):
    name = serializers.CharField(
        max_length=64,
        trim_whitespace=True,
        allow_blank=False,
        help_text="修改后的会话分组名称，最长 64 个字符",
    )


class ConversationCreateRequestSerializer(serializers.Serializer):
    """阶段三只创建默认标题空会话，初始化消息由下一阶段扩展。"""


class ConversationDetailRequestSerializer(serializers.Serializer):
    conversation_uid = serializers.UUIDField(help_text="会话对外 UUID")


class ConversationUpdateRequestSerializer(ConversationDetailRequestSerializer):
    title = serializers.CharField(
        max_length=255,
        trim_whitespace=True,
        allow_blank=False,
        help_text="修改后的会话标题，最长 255 个字符",
    )


class SidebarNodeListRequestSerializer(serializers.Serializer):
    """不传父节点表示根列表，传入时只允许 Group 容器。"""

    parent_node_type = serializers.ChoiceField(
        choices=SidebarNodeType.choices,
        required=False,
        help_text="父容器节点类型；当前仅支持 GROUP，和 parent_node_uid 同时传入",
    )
    parent_node_uid = serializers.UUIDField(
        required=False,
        help_text="父分组对外 UUID；不传表示查询根容器",
    )

    def validate(self, attrs):
        node_type = attrs.get("parent_node_type")
        node_uid = attrs.get("parent_node_uid")
        if bool(node_type) != bool(node_uid):
            raise serializers.ValidationError("父节点类型和 UID 必须同时传入")
        if node_type and node_type != SidebarNodeType.GROUP:
            raise serializers.ValidationError({"parent_node_type": "侧栏父容器只能是分组"})
        return attrs


class SidebarSearchRequestSerializer(serializers.Serializer):
    keyword = serializers.CharField(
        max_length=255,
        trim_whitespace=True,
        allow_blank=False,
        help_text="会话标题搜索关键字，最长 255 个字符",
    )


class SidebarMoveRequestSerializer(serializers.Serializer):
    """将业务节点移到根容器或指定分组的开头/锚点前。"""

    source_node_type = serializers.ChoiceField(
        choices=SidebarNodeType.choices,
        help_text="待移动节点类型",
    )
    source_node_uid = serializers.UUIDField(help_text="待移动业务对象的对外 UUID")
    target_node_type = serializers.ChoiceField(
        choices=SidebarNodeType.choices,
        required=False,
        help_text="目标容器节点类型；仅支持 GROUP，不传表示根容器",
    )
    target_node_uid = serializers.UUIDField(
        required=False,
        help_text="目标分组对外 UUID；和 target_node_type 同时传入",
    )
    before_node_type = serializers.ChoiceField(
        choices=SidebarNodeType.choices,
        required=False,
        help_text="目标锚点类型；移动后来源节点位于该节点之前",
    )
    before_node_uid = serializers.UUIDField(
        required=False,
        help_text="目标锚点业务对象的对外 UUID；不传表示移动到容器开头",
    )

    def validate(self, attrs):
        self._validate_pair(attrs, "target_node_type", "target_node_uid", "目标节点")
        self._validate_pair(attrs, "before_node_type", "before_node_uid", "锚点")

        source_type = attrs["source_node_type"]
        target_type = attrs.get("target_node_type")
        before_type = attrs.get("before_node_type")
        if target_type and target_type != SidebarNodeType.GROUP:
            raise serializers.ValidationError({"target_node_type": "目标容器只能是分组"})
        if source_type == SidebarNodeType.GROUP and target_type:
            raise serializers.ValidationError({"target_node_type": "分组不能嵌套到其他分组"})
        if target_type == SidebarNodeType.GROUP and before_type and before_type != SidebarNodeType.CONVERSATION:
            raise serializers.ValidationError({"before_node_type": "分组内锚点只能是会话"})
        return attrs

    @staticmethod
    def _validate_pair(attrs, type_field: str, uid_field: str, label: str) -> None:
        """两个字段要么都不传，要么同时传入。"""

        if bool(attrs.get(type_field)) != bool(attrs.get(uid_field)):
            raise serializers.ValidationError(f"{label}类型和 UID 必须同时传入")


class SidebarPinRequestSerializer(serializers.Serializer):
    node_type = serializers.ChoiceField(
        choices=SidebarNodeType.choices,
        help_text="待设置置顶状态的节点类型；仅支持 CONVERSATION",
    )
    node_uid = serializers.UUIDField(help_text="会话对外 UUID")
    is_pinned = serializers.BooleanField(help_text="true 表示置顶，false 表示取消置顶")

    def validate_node_type(self, value):
        if value != SidebarNodeType.CONVERSATION:
            raise serializers.ValidationError("只有会话节点可以置顶")
        return value


class ConversationGroupResponseSerializer(serializers.Serializer):
    """分组基础信息，对外只返回不可枚举 UID。"""

    uid = serializers.UUIDField(help_text="会话分组对外 UUID")
    name = serializers.CharField(help_text="会话分组名称")
    created_at = serializers.DateTimeField(help_text="分组创建时间")
    updated_at = serializers.DateTimeField(help_text="分组最后更新时间")


class ConversationResponseSerializer(serializers.Serializer):
    """会话详情；消息数量和内容不属于本阶段响应。"""

    uid = serializers.UUIDField(help_text="会话对外 UUID")
    title = serializers.CharField(help_text="会话标题")
    created_at = serializers.DateTimeField(help_text="会话创建时间")
    updated_at = serializers.DateTimeField(help_text="会话最后更新时间")


class ConversationGroupSummarySerializer(serializers.Serializer):
    uid = serializers.UUIDField(help_text="所属分组对外 UUID")
    name = serializers.CharField(help_text="所属分组名称")


class SidebarNodeResponseSerializer(serializers.Serializer):
    """侧栏多态 DTO，按 node_type 输出分组或会话专属字段。"""

    node_type = serializers.ChoiceField(choices=SidebarNodeType.choices, help_text="侧栏节点类型")
    node_uid = serializers.UUIDField(help_text="分组或会话业务对象的对外 UUID")
    name = serializers.CharField(required=False, help_text="分组节点名称；会话节点不返回")
    title = serializers.CharField(required=False, help_text="会话节点标题；分组节点不返回")
    updated_at = serializers.DateTimeField(required=False, help_text="会话最后更新时间")
    pinned_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="会话置顶时间；未置顶时为 null",
    )
    group = ConversationGroupSummarySerializer(
        required=False,
        allow_null=True,
        help_text="会话所属分组摘要；根会话为 null",
    )
    conversation_count = serializers.IntegerField(
        required=False,
        min_value=0,
        help_text="分组内全部未删除会话数量，包含置顶会话",
    )
    unpinned_conversation_count = serializers.IntegerField(
        required=False,
        min_value=0,
        help_text="分组内未删除且未置顶的会话数量",
    )

    def to_representation(self, instance):
        if instance.node_type == SidebarNodeType.GROUP:
            return {
                "node_type": SidebarNodeType.GROUP,
                "node_uid": str(instance.group.uid),
                "name": instance.group.name,
                "conversation_count": getattr(instance, "conversation_count", 0),
                "unpinned_conversation_count": getattr(instance, "unpinned_conversation_count", 0),
            }
        return self.conversation_representation(instance.conversation, instance)

    @staticmethod
    def conversation_representation(conversation, node):
        """会话项复用同一输出结构，分组摘要由 Node 父关系提供。"""

        group = None
        if node.parent_node_id and node.parent_node.group_id:
            group = {
                "uid": str(node.parent_node.group.uid),
                "name": node.parent_node.group.name,
            }
        return {
            "node_type": SidebarNodeType.CONVERSATION,
            "node_uid": str(conversation.uid),
            "title": conversation.title,
            "updated_at": conversation.updated_at,
            "pinned_at": node.pinned_at,
            "group": group,
        }


class ConversationSearchResponseSerializer(serializers.Serializer):
    """会话搜索只返回会话字段，避免 OpenAPI 混入分组节点专属字段。"""

    node_type = serializers.ChoiceField(choices=SidebarNodeType.choices, help_text="固定为 CONVERSATION")
    node_uid = serializers.UUIDField(help_text="会话对外 UUID")
    title = serializers.CharField(help_text="会话标题")
    updated_at = serializers.DateTimeField(help_text="会话最后更新时间")
    pinned_at = serializers.DateTimeField(allow_null=True, help_text="会话置顶时间；未置顶时为 null")
    group = ConversationGroupSummarySerializer(allow_null=True, help_text="会话所属分组摘要；根会话为 null")
    is_pinned = serializers.BooleanField(help_text="会话当前是否置顶")

    def to_representation(self, instance):
        data = SidebarNodeResponseSerializer.conversation_representation(instance, instance.sidebar_node)
        data["is_pinned"] = instance.sidebar_node.pinned_at is not None
        return data
