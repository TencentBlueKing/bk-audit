"""常见/历史操作上下文（D3 定稿方案）。

常见操作 = 常见的自然语言检索样例，按系统维度缓存于 Redis list，
由 Celery 定时任务从最近成功自然语言消息聚合刷新；
历史操作 = 当前用户最近的自然语言检索，直接查询消息表（按系统过滤）。
"""

import logging
from typing import Iterable

import redis
from django.conf import settings

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas.audit_search import CommonQuerySchema

logger = logging.getLogger(__name__)

COMMON_QUERY_KEY_TEMPLATE = "bk_audit:ai_assistant:common_queries:{system_id}"


def extract_system_ids(systems: Iterable[dict]) -> set[str]:
    """从系统选择快照的系统列表提取 system_id 集合（父消息 scope 校验与历史操作过滤共用）。"""

    return {system.get("system_id") for system in systems if system.get("system_id")}


class CommonQueryStore:
    """常见自然语言样例的 Redis list 存储（最近在前、去重、固定容量）。"""

    def __init__(self, redis_client: redis.Redis | None = None):
        self.redis_client = redis_client or redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            db=int(settings.REDIS_DB),
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )

    @staticmethod
    def build_key(system_id: str) -> str:
        return COMMON_QUERY_KEY_TEMPLATE.format(system_id=system_id)

    def list(self, system_id: str, limit: int) -> list[CommonQuerySchema]:
        """读取系统常见样例；缓存未命中（定时任务未跑过）返回空列表。"""

        try:
            queries = self.redis_client.lrange(self.build_key(system_id), 0, limit - 1)
        except redis.RedisError:
            logger.exception("[CommonQueryStore] redis read failed, system_id=%s", system_id)
            return []
        return [CommonQuerySchema(query_text=query_text) for query_text in queries if query_text]

    def replace(self, system_id: str, queries: Iterable[str]) -> None:
        """整表替换系统样例；容量由调用方按 settings 约束。"""

        pipeline = self.redis_client.pipeline()
        key = self.build_key(system_id)
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
        common = cls.build_common(system_ids=system_ids)
        historical = cls.build_historical(system_ids=system_ids, username=username)
        return common, historical

    @classmethod
    def build_common(cls, *, system_ids: list[str]) -> list[CommonQuerySchema]:
        store = CommonQueryStore()
        results: list[CommonQuerySchema] = []
        seen: set[str] = set()
        for system_id in system_ids:
            for item in store.list(system_id, limit=settings.AI_ASSISTANT_COMMON_QUERY_RETURN_LIMIT):
                if item.query_text in seen:
                    continue
                seen.add(item.query_text)
                results.append(item)
        return results

    @classmethod
    def build_historical(cls, *, system_ids: list[str], username: str) -> list[CommonQuerySchema]:
        """查询当前用户最近自然语言消息（跨会话），按目标系统过滤后去重。"""

        scan_limit = settings.AI_ASSISTANT_HISTORICAL_QUERY_SCAN_LIMIT
        return_limit = settings.AI_ASSISTANT_HISTORICAL_QUERY_LIMIT
        messages = (
            Message.objects.filter(
                created_by=username,
                message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
                status=ExecutionStatus.SUCCESS,
            )
            .order_by("-id")
            .values_list("input_data", "context_data")[:scan_limit]
        )
        allowed_system_ids = set(system_ids)
        results: list[CommonQuerySchema] = []
        seen: set[str] = set()
        for input_data, context_data in messages:
            message_system_ids = cls._extract_message_system_ids(context_data)
            if not allowed_system_ids.intersection(message_system_ids):
                continue
            query_text = (input_data or {}).get("query_text") or ""
            if not query_text or query_text in seen:
                continue
            seen.add(query_text)
            results.append(CommonQuerySchema(query_text=query_text))
            if len(results) >= return_limit:
                break
        return results

    @staticmethod
    def _extract_message_system_ids(context_data: dict | None) -> set[str]:
        """从自然语言消息上下文快照提取其绑定的系统集合。"""

        if not isinstance(context_data, dict):
            return set()
        selection = context_data.get("system_selection") or {}
        return extract_system_ids(selection.get("systems") or [])

    @classmethod
    def refresh_common_queries(cls) -> dict[str, int]:
        """定时任务入口：聚合最近成功自然语言消息，按系统刷新 Redis 缓存。"""

        scan_limit = settings.AI_ASSISTANT_COMMON_QUERY_REFRESH_SCAN_LIMIT
        store_limit = settings.AI_ASSISTANT_COMMON_QUERY_STORE_LIMIT
        messages = (
            Message.objects.filter(
                message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
                status=ExecutionStatus.SUCCESS,
            )
            .order_by("-id")
            .values_list("input_data", "context_data")[:scan_limit]
        )
        # 最近在前；同一样例只保留最新一次出现的顺位
        system_queries: dict[str, list[str]] = {}
        system_seen: dict[str, set[str]] = {}
        for input_data, context_data in messages:
            query_text = (input_data or {}).get("query_text") or ""
            if not query_text:
                continue
            for system_id in cls._extract_message_system_ids(context_data):
                seen = system_seen.setdefault(system_id, set())
                if query_text in seen:
                    continue
                seen.add(query_text)
                system_queries.setdefault(system_id, []).append(query_text)

        store = CommonQueryStore()
        refreshed = 0
        for system_id, queries in system_queries.items():
            try:
                store.replace(system_id, queries[:store_limit])
                refreshed += 1
            except redis.RedisError:
                logger.exception("[OperationContextService] refresh common queries failed, system_id=%s", system_id)
        logger.info(
            "[OperationContextService] common queries refreshed, systems=%d, scanned=%d",
            refreshed,
            len(messages),
        )
        return {"refreshed_systems": refreshed, "scanned_messages": len(messages)}
