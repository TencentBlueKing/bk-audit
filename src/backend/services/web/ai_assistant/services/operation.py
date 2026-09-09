"""常见/历史操作上下文（D3 定稿方案）。

常见操作 = 当前用户常见的自然语言检索样例，按用户 × 系统维度缓存于 Redis list，
由 Celery 定时任务从最近成功检索消息聚合刷新（仅本人消息，用户间互相隔离）；
历史操作 = 当前用户最近的自然语言检索，直接查询消息表（按系统过滤）。

数据源覆盖 NATURAL_LANGUAGE_SEARCH 与 USER_INTENT（统一入口）两类消息：
意图消息仅收录真正产出检索条件的（output 携带 condition + system_id），
SYSTEM_REQUIRED / unrecognized 等引导性结果不进榜单。
"""

import logging
from typing import Iterable

import redis
from django.conf import settings

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas.audit_search import CommonQuerySchema

logger = logging.getLogger(__name__)

COMMON_QUERY_KEY_TEMPLATE = "bk_audit:ai_assistant:common_queries:{system_id}:{username}"


def extract_system_ids(systems: Iterable[dict]) -> set[str]:
    """从系统选择快照的系统列表提取 system_id 集合（父消息 scope 校验与历史操作过滤共用）。"""

    return {system.get("system_id") for system in systems if system.get("system_id")}


class CommonQueryStore:
    """用户常见自然语言样例的 Redis list 存储（最近在前、去重、固定容量、按用户隔离）。"""

    def __init__(self, redis_client: redis.Redis | None = None):
        self.redis_client = redis_client or redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            db=int(settings.REDIS_DB),
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )

    @staticmethod
    def build_key(system_id: str, username: str) -> str:
        return COMMON_QUERY_KEY_TEMPLATE.format(system_id=system_id, username=username)

    def list(self, system_id: str, username: str, limit: int) -> list[CommonQuerySchema]:
        """读取用户在指定系统的常见样例；缓存未命中（定时任务未跑过）返回空列表。"""

        try:
            queries = self.redis_client.lrange(self.build_key(system_id, username), 0, limit - 1)
        except redis.RedisError:
            logger.exception("[CommonQueryStore] redis read failed, system_id=%s, username=%s", system_id, username)
            return []
        return [CommonQuerySchema(query_text=query_text) for query_text in queries if query_text]

    def replace(self, system_id: str, username: str, queries: Iterable[str]) -> None:
        """整表替换用户样例；容量由调用方按 settings 约束。"""

        pipeline = self.redis_client.pipeline()
        key = self.build_key(system_id, username)
        pipeline.delete(key)
        valid_queries = [query_text for query_text in queries if query_text]
        if valid_queries:
            pipeline.rpush(key, *valid_queries)
        pipeline.execute()


class OperationContextService:
    """为系统选择消息组装常见/历史操作上下文。"""

    @classmethod
    def build(cls, *, system_ids: list[str], username: str) -> tuple[list[CommonQuerySchema], list[CommonQuerySchema]]:
        # 操作上下文总闸（设计稿已确认需求，默认开启；关闭时选择消息不携带常见/历史操作）
        if not getattr(settings, "AI_ASSISTANT_OPERATION_RANKING_ENABLED", True):
            return [], []
        common = cls.build_common(system_ids=system_ids, username=username)
        historical = cls.build_historical(system_ids=system_ids, username=username)
        return common, historical

    @classmethod
    def build_common(cls, *, system_ids: list[str], username: str) -> list[CommonQuerySchema]:
        """读取当前用户在所选系统的常见样例（跨系统去重；用户间互相隔离）。"""

        store = CommonQueryStore()
        results: list[CommonQuerySchema] = []
        seen: set[str] = set()
        for system_id in system_ids:
            for item in store.list(system_id, username, limit=settings.AI_ASSISTANT_COMMON_QUERY_RETURN_LIMIT):
                if item.query_text in seen:
                    continue
                seen.add(item.query_text)
                results.append(item)
        return results

    @classmethod
    def build_historical(cls, *, system_ids: list[str], username: str) -> list[CommonQuerySchema]:
        """查询当前用户最近自然语言检索（NL 与 USER_INTENT 统一入口），按目标系统过滤后去重。"""

        scan_limit = settings.AI_ASSISTANT_HISTORICAL_QUERY_SCAN_LIMIT
        return_limit = settings.AI_ASSISTANT_HISTORICAL_QUERY_LIMIT
        allowed_system_ids = set(system_ids)
        results: list[CommonQuerySchema] = []
        seen: set[str] = set()
        for query_text, message_system_ids, _created_by in cls._iter_recent_queries(scan_limit, username=username):
            if not allowed_system_ids.intersection(message_system_ids):
                continue
            if query_text in seen:
                continue
            seen.add(query_text)
            results.append(CommonQuerySchema(query_text=query_text))
            if len(results) >= return_limit:
                break
        return results

    @classmethod
    def _iter_recent_queries(cls, scan_limit: int, username: str | None = None):
        """迭代最近成功检索样例（NL + USER_INTENT 统一入口），产出 (query_text, system_ids, created_by)。

        - NL 消息：系统取 context_data.system_selection.systems
        - USER_INTENT：系统取 output_data.system_id；仅 condition 非空（真正产出检索并续链）
          才收录——SYSTEM_REQUIRED / unrecognized 等引导性输出不是检索，不进榜单
        """

        filters = {
            "message_type__in": [MessageType.NATURAL_LANGUAGE_SEARCH, MessageType.USER_INTENT],
            "status": ExecutionStatus.SUCCESS,
        }
        if username:
            filters["created_by"] = username
        messages = (
            Message.objects.filter(**filters)
            .order_by("-id")
            .values_list("message_type", "input_data", "context_data", "output_data", "created_by")[:scan_limit]
        )
        for message_type, input_data, context_data, output_data, created_by in messages:
            query_text = (input_data or {}).get("query_text") or ""
            if not query_text:
                continue
            if message_type == MessageType.USER_INTENT:
                output = output_data if isinstance(output_data, dict) else {}
                system_id = str(output.get("system_id") or "")
                if output.get("condition") is None or not system_id:
                    continue
                system_ids = {system_id}
            else:
                system_ids = cls._extract_message_system_ids(context_data)
                if not system_ids:
                    continue
            yield query_text, system_ids, created_by

    @staticmethod
    def _extract_message_system_ids(context_data: dict | None) -> set[str]:
        """从自然语言消息上下文快照提取其绑定的系统集合。"""

        if not isinstance(context_data, dict):
            return set()
        selection = context_data.get("system_selection") or {}
        return extract_system_ids(selection.get("systems") or [])

    @classmethod
    def refresh_common_queries(cls) -> dict[str, int]:
        """定时任务入口：聚合最近成功检索消息（NL + USER_INTENT），按用户 × 系统刷新 Redis 缓存。"""

        scan_limit = settings.AI_ASSISTANT_COMMON_QUERY_REFRESH_SCAN_LIMIT
        store_limit = settings.AI_ASSISTANT_COMMON_QUERY_STORE_LIMIT
        # 最近在前；同一用户同一样例只保留最新一次出现的顺位（用户间天然隔离）
        user_system_queries: dict[tuple[str, str], list[str]] = {}
        user_system_seen: dict[tuple[str, str], set[str]] = {}
        scanned = 0
        for query_text, system_ids, created_by in cls._iter_recent_queries(scan_limit):
            scanned += 1
            for system_id in system_ids:
                key = (created_by, system_id)
                seen = user_system_seen.setdefault(key, set())
                if query_text in seen:
                    continue
                seen.add(query_text)
                user_system_queries.setdefault(key, []).append(query_text)

        store = CommonQueryStore()
        refreshed = 0
        for (username, system_id), queries in user_system_queries.items():
            try:
                store.replace(system_id, username, queries[:store_limit])
                refreshed += 1
            except redis.RedisError:
                logger.exception(
                    "[OperationContextService] refresh common queries failed, system_id=%s, username=%s",
                    system_id,
                    username,
                )
        logger.info(
            "[OperationContextService] common queries refreshed, user_systems=%d, scanned=%d",
            refreshed,
            scanned,
        )
        return {"refreshed_systems": refreshed, "scanned_messages": scanned}
