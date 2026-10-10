"""AI 助手测试数据工厂。

新建会话资源必须属于 concrete scope；普通业务测试默认绑定 scene:1。
scope 行为测试应显式传入目标 scope，避免默认值掩盖隔离错误。
"""

from typing import Any

from services.web.ai_assistant.models import Conversation, ConversationGroup
from services.web.common.constants import ScopeType

DEFAULT_SCOPE_TYPE = ScopeType.SCENE.value
DEFAULT_SCOPE_ID = "1"


def create_conversation(
    *, scope_type: str = DEFAULT_SCOPE_TYPE, scope_id: str = DEFAULT_SCOPE_ID, **fields: Any
) -> Conversation:
    """创建带 concrete scope 的会话。

    Args:
        scope_type: 资源绑定类型，默认为测试场景。
        scope_id: 资源绑定 ID，默认为第一个场景。
        **fields: 其余 Conversation ORM 创建参数。

    Returns:
        已保存的 Conversation。
    """

    return Conversation.objects.create(scope_type=scope_type, scope_id=scope_id, **fields)


def create_conversation_group(
    *, scope_type: str = DEFAULT_SCOPE_TYPE, scope_id: str = DEFAULT_SCOPE_ID, **fields: Any
) -> ConversationGroup:
    """创建带 concrete scope 的分组。

    Args:
        scope_type: 资源绑定类型，默认为测试场景。
        scope_id: 资源绑定 ID，默认为第一个场景。
        **fields: 其余 ConversationGroup ORM 创建参数。

    Returns:
        已保存的 ConversationGroup。
    """

    return ConversationGroup.objects.create(scope_type=scope_type, scope_id=scope_id, **fields)
