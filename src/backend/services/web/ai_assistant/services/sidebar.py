import time

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import OperationalError, transaction
from django.db.models import Count, F, Q, QuerySet
from django.utils import timezone

from services.web.ai_assistant.constants import (
    MYSQL_DEADLOCK_ERROR_CODE,
    SIDEBAR_MOVE_DEADLOCK_MAX_RETRIES,
    SIDEBAR_MOVE_DEADLOCK_RETRY_INTERVAL_SECONDS,
    SidebarNodeType,
)
from services.web.ai_assistant.exceptions import (
    ConversationGroupNotFound,
    InvalidSidebarAnchor,
    InvalidSidebarContainer,
    SidebarNodeNotFound,
    SidebarNodeNotMovable,
)
from services.web.ai_assistant.models import (
    Conversation,
    ConversationGroup,
    ConversationSidebarNode,
)


class ConversationSidebarService:
    """维护用户侧栏 Node 的容器、顺序和展示状态。"""

    def __init__(self, *, user: str):
        """绑定当前操作用户，侧栏内部查询默认继承该用户边界。"""

        self.user = user

    def _container_queryset(self, *, parent_node_id: int | None) -> QuerySet[ConversationSidebarNode]:
        """精确限定当前用户和一个父容器，避免跨容器更新。"""

        queryset = ConversationSidebarNode.objects.filter(created_by=self.user)
        if parent_node_id is None:
            return queryset.filter(parent_node_id__isnull=True)
        return queryset.filter(parent_node_id=parent_node_id)

    @transaction.atomic
    def create_node(
        self,
        *,
        group: ConversationGroup | None = None,
        conversation: Conversation | None = None,
    ) -> ConversationSidebarNode:
        """为一个分组或会话创建根 Node，新节点默认位于最前。"""

        self._validate_create_target(group=group, conversation=conversation)
        top_node = self._container_queryset(parent_node_id=None).order_by("-position", "-id").first()
        node = ConversationSidebarNode(
            node_type=SidebarNodeType.GROUP if group else SidebarNodeType.CONVERSATION,
            group=group,
            conversation=conversation,
            position=(top_node.position + 1) if top_node else 1,
            created_by=self.user,
            updated_at=timezone.now(),
            updated_by=self.user,
        )
        node.full_clean()
        # 服务已明确传入操作者，避免 OperateRecordModel 从请求上下文再次覆盖。
        node.save(update_record=False, force_insert=True)
        return node

    def list_pinned(self) -> QuerySet[ConversationSidebarNode]:
        """返回当前用户全部置顶会话，置顶时间越新越靠前。"""

        return (
            ConversationSidebarNode.objects.filter(
                created_by=self.user,
                node_type=SidebarNodeType.CONVERSATION,
                conversation__is_deleted=False,
                pinned_at__isnull=False,
            )
            .select_related("conversation", "parent_node__group")
            .order_by("-pinned_at", "-id")
        )

    def list_nodes(
        self,
        *,
        parent_group_uid: str | None = None,
    ) -> QuerySet[ConversationSidebarNode]:
        """返回根列表或指定分组中的普通 Node，后端直接排除置顶会话。"""

        parent_node_id = None
        if parent_group_uid is not None:
            parent_node_id = self._resolve_node(
                node_type=SidebarNodeType.GROUP,
                node_uid=parent_group_uid,
            ).id
        return (
            self._container_queryset(parent_node_id=parent_node_id)
            .filter(pinned_at__isnull=True)
            .filter(
                # 分组节点没有 conversation；会话节点必须仍处于未删除状态。
                Q(node_type=SidebarNodeType.GROUP)
                | Q(node_type=SidebarNodeType.CONVERSATION, conversation__is_deleted=False)
            )
            .annotate(
                # 数量直接挂在 Group Node 上，DTO 序列化时不会逐组查询。
                conversation_count=Count(
                    "children",
                    filter=Q(
                        children__node_type=SidebarNodeType.CONVERSATION,
                        children__created_by=self.user,
                        children__conversation__is_deleted=False,
                    ),
                ),
                unpinned_conversation_count=Count(
                    "children",
                    filter=Q(
                        children__node_type=SidebarNodeType.CONVERSATION,
                        children__created_by=self.user,
                        children__conversation__is_deleted=False,
                        children__pinned_at__isnull=True,
                    ),
                ),
            )
            .select_related("group", "conversation", "parent_node__group")
            .order_by("-position", "-id")
        )

    def search_conversations(self, *, keyword: str) -> QuerySet[Conversation]:
        """标题搜索包含置顶会话，但不使用侧栏 position 排序。"""

        return (
            Conversation.objects.filter(created_by=self.user, title__icontains=keyword)
            .select_related("sidebar_node__parent_node__group")
            .order_by("-updated_at", "-id")
        )

    def set_pinned(
        self,
        *,
        conversation_uid: str,
        is_pinned: bool,
    ) -> ConversationSidebarNode:
        """显式设置会话置顶状态；重复请求不刷新置顶时间。"""

        node = self._resolve_node(
            node_type=SidebarNodeType.CONVERSATION,
            node_uid=conversation_uid,
        )
        if (node.pinned_at is not None) == is_pinned:
            return node
        operation_time = timezone.now()
        node.pinned_at = operation_time if is_pinned else None
        node.updated_at = operation_time
        node.updated_by = self.user
        node.save(
            update_record=False,
            update_fields=["pinned_at", "updated_by", "updated_at"],
        )
        return node

    def move(
        self,
        *,
        source_node_type: str,
        source_node_uid: str,
        target_node_type: str | None = None,
        target_node_uid: str | None = None,
        before_node_type: str | None = None,
        before_node_uid: str | None = None,
    ) -> ConversationSidebarNode:
        """
        执行完整 move 事务，将节点移动到目标容器的指定位置。

        设计理念
        --------
        1. **用户级隔离**：所有查询和范围更新均限定实例绑定的 user，
           精确 Node 锁只命中当前用户行，不引入应用级跨用户锁。

        2. **稀疏序号 + 复合排序键**：排序键为 (-position, -id)，position 越大越靠前，
           相同 position 时 id 越大越靠前。插入时优先寻找整数空位（O(1) 单行更新），
           仅在无空位时才批量平移相邻节点。空位判定条件为 predecessor.position -
           anchor.position >= 2，确保插入值能独占一个 position 层级，不依赖 id 大小
           来决定最终顺序。

        3. **乐观读 + 悲观锁二次校验**：先无锁解析业务 UID 到内部 Node（快速失败），
           再按主键升序逐个 SELECT FOR UPDATE 加行锁，锁定后重新校验 pinned_at 和
           parent_node_id 等关键状态，消除 TOCTOU 竞态。

        4. **固定锁顺序**：move 最多涉及 source、target_parent、anchor 三个 Node，
           始终按主键 id 升序加锁，避免 ABBA 死锁。

        5. **死锁重试**：同一用户并发拖拽时，批量平移的范围 UPDATE 可能因 InnoDB
           next-key lock 产生死锁。外层捕获 MySQL 1213 错误码后线性退避重试（最多
           重试 2 次），每次从头重新解析以获取最新状态。

        6. **幂等性**：重复拖动到相同位置时检测到 source 已是锚点的直接前驱，直接
           返回而不写入任何排序字段，避免无意义的行锁竞争和 binlog 膨胀。
        """

        for retry_count in range(SIDEBAR_MOVE_DEADLOCK_MAX_RETRIES + 1):
            try:
                return self._move(
                    source_node_type=source_node_type,
                    source_node_uid=source_node_uid,
                    target_node_type=target_node_type,
                    target_node_uid=target_node_uid,
                    before_node_type=before_node_type,
                    before_node_uid=before_node_uid,
                )
            except OperationalError as error:
                is_deadlock = bool(error.args) and error.args[0] == MYSQL_DEADLOCK_ERROR_CODE
                if not is_deadlock or retry_count >= SIDEBAR_MOVE_DEADLOCK_MAX_RETRIES:
                    raise
                time.sleep(SIDEBAR_MOVE_DEADLOCK_RETRY_INTERVAL_SECONDS * (retry_count + 1))
        raise AssertionError("unreachable")

    @transaction.atomic
    def _move(
        self,
        *,
        source_node_type: str,
        source_node_uid: str,
        target_node_type: str | None = None,
        target_node_uid: str | None = None,
        before_node_type: str | None = None,
        before_node_uid: str | None = None,
    ) -> ConversationSidebarNode:
        """
        将 Node 移到目标容器开头，或插入目标容器指定 Node（anchor）之前。

        执行流程：
        1. 无锁解析 source / target_parent / anchor（快速校验参数合法性）
        2. 按主键升序加行锁，二次校验节点状态（防止并发修改导致的不一致）
        3. 计算目标 position（优先利用空位，必要时平移相邻节点）
        4. 原子更新 source 的 parent_node 和 position
        """

        source = self._resolve_node(
            node_type=source_node_type,
            node_uid=source_node_uid,
        )
        if source.pinned_at is not None:
            raise SidebarNodeNotMovable()

        target_parent = self._resolve_target_parent(
            source=source,
            target_node_type=target_node_type,
            target_node_uid=target_node_uid,
        )
        target_parent_id = target_parent.id if target_parent else None
        anchor = self._resolve_anchor(
            before_node_type=before_node_type,
            before_node_uid=before_node_uid,
            target_parent_id=target_parent_id,
        )
        # 按主键升序加行锁，保证全局锁顺序一致，避免 ABBA 死锁。
        source, target_parent, anchor = self._lock_move_nodes(
            source=source,
            target_parent=target_parent,
            anchor=anchor,
        )
        # 二次校验：加锁后重新检查关键状态，消除乐观读与加锁之间的 TOCTOU 竞态。
        target_parent_id = target_parent.id if target_parent else None
        if source.pinned_at is not None:
            raise SidebarNodeNotMovable()
        if anchor is not None and (anchor.parent_node_id != target_parent_id or anchor.pinned_at is not None):
            raise InvalidSidebarAnchor()
        if anchor is not None and anchor.id == source.id:
            if source.parent_node_id != target_parent_id:
                raise InvalidSidebarAnchor()
            return self._node_for_response(node=source)

        target_nodes = self._container_queryset(parent_node_id=target_parent_id).exclude(id=source.id)
        target_position = self._make_target_position(
            source=source,
            target_nodes=target_nodes,
            target_parent_id=target_parent_id,
            anchor=anchor,
        )
        if target_position is None:
            return self._node_for_response(node=source)

        source.parent_node = target_parent
        source.position = target_position
        source.updated_at = timezone.now()
        source.updated_by = self.user
        source.full_clean()
        source.save(
            update_record=False,
            update_fields=["parent_node", "position", "updated_by", "updated_at"],
        )
        return self._node_for_response(node=source)

    @staticmethod
    def _make_target_position(
        *,
        source: ConversationSidebarNode,
        target_nodes: QuerySet[ConversationSidebarNode],
        target_parent_id: int | None,
        anchor: ConversationSidebarNode | None,
    ) -> int | None:
        """
        按稳定排序键 (-position, -id) 计算插入位置，仅在没有整数空位时平移锚点前缀。

        返回 None 表示 source 已在目标位置，无需任何写操作（幂等保护）。

        三种路径：
        1. 无锚点，移到容器最前：position = top_node.position + 1
        2. 有锚点，锚点前有空位：position = anchor.position + 1（只更新 source 一行）
        3. 有锚点，锚点前无空位：批量平移锚点前方所有节点的 position，再插入

        空位判定：predecessor.position - anchor.position >= 2
        ─────────────────────────────────────────────────────
        排序键是 (position, id) 复合键。如果差值仅为 1，anchor.position + 1 ==
        predecessor.position，source 与 predecessor 的 position 相同，最终顺序将
        退化为比较 id 大小——而 id 是自增的、不可控的，无法保证正确的相对顺序。
        差值 >= 2 确保 anchor.position + 1 严格小于 predecessor.position，使 source
        独占一个 position 层级。

        平移偏移量选择：
        - predecessor.position > anchor.position（差 1）：平移 1 位即可腾出空位
        - predecessor.position == anchor.position（靠 id 区分）：需平移 2 位，否则
          平移后 predecessor 与 source 的 position 再次相同
        """

        same_container = source.parent_node_id == target_parent_id
        if anchor is None:
            top_node = target_nodes.order_by("-position", "-id").first()
            if same_container and (top_node is None or (source.position, source.id) > (top_node.position, top_node.id)):
                return None
            return (top_node.position + 1) if top_node else 1

        before_anchor = Q(position__gt=anchor.position) | Q(position=anchor.position, id__gt=anchor.id)
        after_source = Q(position__lt=source.position) | Q(position=source.position, id__lt=source.id)
        source_is_before_anchor = (source.position, source.id) > (anchor.position, anchor.id)
        if (
            same_container
            and source_is_before_anchor
            and not target_nodes.filter(before_anchor & after_source).exists()
        ):
            # 来源已是锚点的直接前驱，重复拖动不改写任何排序字段。
            return None

        # predecessor 是锚点在排序键上的直接前驱（position 最小且紧邻 anchor 前方的节点）。
        predecessor = target_nodes.filter(before_anchor).order_by("position", "id").first()
        if predecessor is None or predecessor.position - anchor.position >= 2:
            # 常规路径：锚点前存在整数空位，只需更新 source 一行，O(1) 写入。
            return anchor.position + 1

        # 无空位路径：批量平移锚点前方所有节点的 position。
        # - 连续序号（差 1）：平移 1 位即可腾出独立空位。
        # - 重复序号（差 0，靠 id 区分）：需平移 2 位，否则 source 与 predecessor
        #   的 position 相同，顺序退化为比较 id，结果不可控。
        # 注意：此 UPDATE 使用 _update_record=False 跳过 updated_at/updated_by，
        # 避免"用户未主动操作的节点"显示为被修改，同时减少不必要的 IO。
        offset = 1 if predecessor.position > anchor.position else 2
        target_nodes.filter(before_anchor).update(_update_record=False, position=F("position") + offset)
        return anchor.position + 1

    def _lock_move_nodes(
        self,
        *,
        source: ConversationSidebarNode,
        target_parent: ConversationSidebarNode | None,
        anchor: ConversationSidebarNode | None,
    ) -> tuple[ConversationSidebarNode, ConversationSidebarNode | None, ConversationSidebarNode | None]:
        """按主键固定顺序锁定 move 涉及的精确 Node，避免关联查询和反向加锁。"""

        nodes = [node for node in (source, target_parent, anchor) if node is not None]
        locked_nodes = {}
        # move 最多涉及三个 Node；逐主键加锁比依赖 IN 查询的执行计划更容易保证锁顺序。
        for node_id in sorted({node.id for node in nodes}):
            locked_node = self._lock_node(node_id=node_id)
            if locked_node is not None:
                locked_nodes[node_id] = locked_node

        if source.id not in locked_nodes:
            raise SidebarNodeNotFound()
        if target_parent is not None and target_parent.id not in locked_nodes:
            raise ConversationGroupNotFound()
        if anchor is not None and anchor.id not in locked_nodes:
            raise InvalidSidebarAnchor()
        return (
            locked_nodes[source.id],
            locked_nodes[target_parent.id] if target_parent is not None else None,
            locked_nodes[anchor.id] if anchor is not None else None,
        )

    def _node_for_response(
        self,
        *,
        node: ConversationSidebarNode,
    ) -> ConversationSidebarNode:
        """Group 移动后补齐聚合计数，会话 Node 直接复用已加载实例。"""

        if node.node_type == SidebarNodeType.GROUP:
            return self.list_nodes().get(id=node.id)
        return node

    def _resolve_target_parent(
        self,
        *,
        source: ConversationSidebarNode,
        target_node_type: str | None,
        target_node_uid: str | None,
    ) -> ConversationSidebarNode | None:
        """空目标表示根容器；非空目标只允许当前用户的分组。"""

        if bool(target_node_type) != bool(target_node_uid):
            raise InvalidSidebarContainer()
        if target_node_type is None:
            return None
        if target_node_type != SidebarNodeType.GROUP or source.node_type == SidebarNodeType.GROUP:
            raise InvalidSidebarContainer()
        try:
            return self._resolve_node(
                node_type=SidebarNodeType.GROUP,
                node_uid=target_node_uid,
            )
        except SidebarNodeNotFound as error:
            raise ConversationGroupNotFound() from error

    def _resolve_anchor(
        self,
        *,
        before_node_type: str | None,
        before_node_uid: str | None,
        target_parent_id: int | None,
    ) -> ConversationSidebarNode | None:
        """锚点必须位于目标容器且未置顶。"""

        if bool(before_node_type) != bool(before_node_uid):
            raise InvalidSidebarAnchor()
        if before_node_type is None:
            return None
        try:
            anchor = self._resolve_node(
                node_type=before_node_type,
                node_uid=before_node_uid,
            )
        except SidebarNodeNotFound as error:
            raise InvalidSidebarAnchor() from error
        if anchor.parent_node_id != target_parent_id or anchor.pinned_at is not None:
            raise InvalidSidebarAnchor()
        return anchor

    def _resolve_node(
        self,
        *,
        node_type: str,
        node_uid: str,
    ) -> ConversationSidebarNode:
        """使用业务对象 UID 解析内部 Node，不向调用方暴露可枚举 ID。"""

        queryset = ConversationSidebarNode.objects.filter(created_by=self.user, node_type=node_type)
        if node_type == SidebarNodeType.GROUP:
            queryset = queryset.filter(group__uid=node_uid)
        elif node_type == SidebarNodeType.CONVERSATION:
            queryset = queryset.filter(conversation__uid=node_uid, conversation__is_deleted=False)
        else:
            raise SidebarNodeNotFound()
        try:
            node = queryset.select_related("group", "conversation", "parent_node__group").first()
        except DjangoValidationError as error:
            raise SidebarNodeNotFound() from error
        if node is None:
            raise SidebarNodeNotFound()
        return node

    def _lock_node(self, *, node_id: int) -> ConversationSidebarNode | None:
        """只按主键锁定当前用户的单个 Node，不联表、不获取容器 gap lock。"""

        return ConversationSidebarNode.objects.select_for_update().filter(id=node_id, created_by=self.user).first()

    def _validate_create_target(
        self,
        *,
        group: ConversationGroup | None,
        conversation: Conversation | None,
    ) -> None:
        """要求业务对象唯一、已入库且归属当前用户。"""

        if not self.user or (group is None) == (conversation is None):
            raise InvalidSidebarContainer()
        if group is not None:
            if (
                group.created_by != self.user
                or not ConversationGroup.objects.filter(
                    id=group.id,
                    created_by=self.user,
                ).exists()
            ):
                raise InvalidSidebarContainer()
            return
        if (
            conversation.created_by != self.user
            or conversation.is_deleted
            or not Conversation.objects.filter(id=conversation.id, created_by=self.user).exists()
        ):
            raise InvalidSidebarContainer()
