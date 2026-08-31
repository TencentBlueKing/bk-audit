from bk_resource import Resource
from django.utils.translation import gettext_lazy

from core.models import get_request_username
from services.web.ai_assistant.serializers.conversation import (
    ConversationCreateRequestSerializer,
    ConversationCreateResponseSerializer,
    ConversationDetailRequestSerializer,
    ConversationGroupCreateRequestSerializer,
    ConversationGroupDetailRequestSerializer,
    ConversationGroupResponseSerializer,
    ConversationGroupUpdateRequestSerializer,
    ConversationResponseSerializer,
    ConversationSearchResponseSerializer,
    ConversationUpdateRequestSerializer,
    SidebarMoveRequestSerializer,
    SidebarNodeListRequestSerializer,
    SidebarNodeResponseSerializer,
    SidebarPinRequestSerializer,
    SidebarSearchRequestSerializer,
)
from services.web.ai_assistant.services import (
    ConversationService,
    ConversationSidebarService,
)


class AIAssistantResource(Resource):
    """AI 助手平台资源基类，领域权限统一使用当前请求用户。"""

    tags = ["AIAssistant"]


class CreateConversationGroup(AIAssistantResource):
    """创建一个可为空的会话分组，并在侧栏根列表生成对应分组节点。"""

    name = gettext_lazy("创建会话分组")
    RequestSerializer = ConversationGroupCreateRequestSerializer
    ResponseSerializer = ConversationGroupResponseSerializer

    def perform_request(self, validated_request_data):
        return ConversationService(user=get_request_username()).create_group(name=validated_request_data["name"])


class UpdateConversationGroup(AIAssistantResource):
    """重命名当前用户的会话分组，不改变组内会话及侧栏顺序。"""

    name = gettext_lazy("重命名会话分组")
    RequestSerializer = ConversationGroupUpdateRequestSerializer
    ResponseSerializer = ConversationGroupResponseSerializer

    def perform_request(self, validated_request_data):
        return ConversationService(user=get_request_username()).rename_group(**validated_request_data)


class DeleteConversationGroup(AIAssistantResource):
    """删除会话分组，并同步软删除组内会话及其侧栏节点。"""

    name = gettext_lazy("删除会话分组")
    RequestSerializer = ConversationGroupDetailRequestSerializer

    def perform_request(self, validated_request_data):
        ConversationService(user=get_request_username()).delete_group(**validated_request_data)


class CreateConversation(AIAssistantResource):
    """创建会话；可携带系统选择初始化消息，并在同一事务中原子落库。"""

    name = gettext_lazy("创建会话")
    RequestSerializer = ConversationCreateRequestSerializer
    ResponseSerializer = ConversationCreateResponseSerializer

    def perform_request(self, validated_request_data):
        creation = ConversationService(user=get_request_username()).create_conversation(
            title=validated_request_data["title"],
            initial_message=validated_request_data.get("initial_message"),
        )
        # 保持 Django Model 响应路径，使 bk_resource 使用实例序列化并保留 UUID 输出格式。
        creation.conversation.initial_message = creation.initial_message
        return creation.conversation


class GetConversation(AIAssistantResource):
    """获取当前用户未删除的会话基础信息。"""

    name = gettext_lazy("获取会话详情")
    RequestSerializer = ConversationDetailRequestSerializer
    ResponseSerializer = ConversationResponseSerializer

    def perform_request(self, validated_request_data):
        return ConversationService(user=get_request_username()).get_conversation(**validated_request_data)


class UpdateConversation(AIAssistantResource):
    """重命名当前用户的会话，不改变消息、分组和侧栏顺序。"""

    name = gettext_lazy("重命名会话")
    RequestSerializer = ConversationUpdateRequestSerializer
    ResponseSerializer = ConversationResponseSerializer

    def perform_request(self, validated_request_data):
        return ConversationService(user=get_request_username()).rename_conversation(**validated_request_data)


class DeleteConversation(AIAssistantResource):
    """软删除会话并移除对应侧栏节点；一期不支持恢复。"""

    name = gettext_lazy("删除会话")
    RequestSerializer = ConversationDetailRequestSerializer

    def perform_request(self, validated_request_data):
        ConversationService(user=get_request_username()).delete_conversation(**validated_request_data)


class ClearConversations(AIAssistantResource):
    """清空当前用户的全部会话和会话节点，但保留已创建的空分组。"""

    name = gettext_lazy("清空会话")

    def perform_request(self, validated_request_data):
        ConversationService(user=get_request_username()).clear_conversations()


class ListPinnedConversations(AIAssistantResource):
    """一次性返回全部置顶会话；这些会话不会重复出现在普通侧栏节点列表。"""

    name = gettext_lazy("获取置顶会话")
    ResponseSerializer = SidebarNodeResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        return ConversationSidebarService(user=get_request_username()).list_pinned()


class ListConversationSidebarNodes(AIAssistantResource):
    """分页获取根列表或指定分组内的混排侧栏节点，按当前相对顺序返回。"""

    name = gettext_lazy("获取侧栏节点")
    RequestSerializer = SidebarNodeListRequestSerializer
    # 分页接口保留 QuerySet 给 ViewSet 先做数据库切片，再序列化当前页。
    serializer_class = SidebarNodeResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        parent_group_uid = validated_request_data.get("parent_node_uid")
        return ConversationSidebarService(user=get_request_username()).list_nodes(
            parent_group_uid=str(parent_group_uid) if parent_group_uid else None,
        )


class SearchConversations(AIAssistantResource):
    """按标题分页搜索当前用户的未删除会话，结果包含所属分组等定位信息。"""

    name = gettext_lazy("搜索会话")
    RequestSerializer = SidebarSearchRequestSerializer
    serializer_class = ConversationSearchResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        return ConversationSidebarService(user=get_request_username()).search_conversations(**validated_request_data)


class MoveConversationSidebarNode(AIAssistantResource):
    """
    移动侧栏会话或分组 Node，并返回移动后的 Node 摘要。

    前端按以下规则组装请求：

    - `source_node_type/source_node_uid` 必填，`source_node_type` 可为 `GROUP` 或 `CONVERSATION`；UID 使用业务 UUID，
      不是内部 Node ID。分组来源只能留在根容器，不能嵌套到其他分组。
    - `target_node_type/target_node_uid` 必须成对出现，只用于指定目标容器；省略表示根容器，传 `GROUP + group_uid`
      表示该分组。会话可以在根容器和分组之间移动。
    - 不传 `before_*` 和 `after_*` 时移动到目标容器开头；两组锚点必须成对出现且不能同时传入。
    - 传 `before_*` 时，来源节点落在锚点之前；传 `after_*` 时，来源节点落在锚点之后。
      根容器的锚点可以是分组或未置顶会话，分组容器的锚点只能是该分组内的会话。
    - `after` 按完整容器物理顺序计算，置顶节点虽然不显示在普通列表中，仍可能作为隐式后继；例如
      `A、pinned、tail` 中执行 `source after A`，结果是 `A、source、pinned、tail`。置顶来源或置顶节点不能
      作为可移动来源或显式锚点。
    - 来源与锚点相同、或重复提交已经完成的移动，均按幂等成功处理；`after` 锚点已是物理末尾时，来源进入容器末尾。

    常见请求示例：

    ```json
    {
      "source_node_type": "CONVERSATION",
      "source_node_uid": "source-conversation-uuid",
      "target_node_type": "GROUP",
      "target_node_uid": "group-uuid",
      "after_node_type": "CONVERSATION",
      "after_node_uid": "anchor-conversation-uuid"
    }
    ```

    上例表示将会话移动到指定分组中锚点会话之后；移动到根容器时省略 `target_node_*`，移动到容器开头时再省略
    两组锚点字段。接口成功后以响应中的 Node 摘要和重新读取的容器列表为准更新前端顺序。
    """

    name = gettext_lazy("移动侧栏节点")
    RequestSerializer = SidebarMoveRequestSerializer
    ResponseSerializer = SidebarNodeResponseSerializer

    def perform_request(self, validated_request_data):
        return ConversationSidebarService(user=get_request_username()).move(**validated_request_data)


class PinConversationSidebarNode(AIAssistantResource):
    """按会话节点设置或取消置顶；置顶不改变节点原分组及普通列表顺序。"""

    name = gettext_lazy("设置会话置顶状态")
    RequestSerializer = SidebarPinRequestSerializer
    ResponseSerializer = SidebarNodeResponseSerializer

    def perform_request(self, validated_request_data):
        return ConversationSidebarService(user=get_request_username()).set_pinned(
            conversation_uid=validated_request_data["node_uid"],
            is_pinned=validated_request_data["is_pinned"],
        )
