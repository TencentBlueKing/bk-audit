"""常见/历史操作上下文（D3 定稿方案；常用操作已高频化改造）。

常见操作 = 当前用户的高频自然语言检索样例（"常用 = 高频"，产品确认）：
- 天桶 ZSet 计数（member=query_text 原文，score=当日出现次数），
  由 Celery 定时任务每小时重建"当天"桶（幂等，只扫当天消息，量小）；
- 读取时合并统计窗口内的天桶并按线性时间衰减加权（今天 1.0 → 窗口边缘 ~0.07），
  持续使用 > 集中突击 > 历史热点，防老操作永久霸榜；
- 桶 TTL = 窗口 + 2 天，Redis 自动滚动清理，内存有界；次要功能全链路降级安全
  （Redis 异常返回空列表，不阻断系统选择消息主流程）。
历史操作 = 当前用户最近的自然语言检索，直接查询消息表并按 Conversation scope 过滤。

数据源是 USER_INTENT：仅收录真正产出检索条件的消息
（存在成功的来源 LOG_SEARCH，或历史输出仍携带 condition 与 system_id）。
SYSTEM_REQUIRED / unrecognized 等引导性结果不进榜单。
"""

import logging
from datetime import date, datetime, timedelta
from typing import Iterable, Iterator

import redis
from django.conf import settings
from django.utils import timezone

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas.audit_search import CommonQuerySchema

logger = logging.getLogger(__name__)

# v3：按会话绑定 scope 隔离天桶；旧 key 不再读写或主动清理。
COMMON_QUERY_BUCKET_KEY_TEMPLATE = "bk_audit:ai_assistant:common_queries_v3:{scope_type}:{scope_id}:{username}:d{day}"


def extract_system_ids(systems: Iterable[dict]) -> set[str]:
    """从系统选择快照的系统列表提取 system_id 集合（父消息 scope 校验与历史操作过滤共用）。"""

    return {system.get("system_id") for system in systems if system.get("system_id")}


class CommonQueryStore:
    """用户高频检索样例的天桶 ZSet 存储（资源受控 + 全链路降级安全的次要功能）。

    - 天桶：member=query_text 原文，score=当日出现次数；TTL=窗口+2 天自动滚动清理
    - 写：replace_today 原子重建当天桶（MULTI：delete+zadd+expire），幂等可重投
      （delete+rebuild 而非累加，任务重复执行不产生重复计数副作用）
    - 读：list_top 一次 pipeline 拉窗口内当前 scope 的天桶（≤ 窗口个小 ZSet），
      Python 端线性衰减加权合并 top K——不依赖 Redis 6.2+ 的 ZUNION，
      无临时 key 残留风险；同一 scope 内跨系统的同句合并频次
    """

    def __init__(self, redis_client: redis.Redis | None = None):
        self.redis_client = redis_client or redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            db=int(settings.REDIS_DB),
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )

    @staticmethod
    def build_bucket_key(scope_type: str, scope_id: str, username: str, day: date) -> str:
        return COMMON_QUERY_BUCKET_KEY_TEMPLATE.format(
            scope_type=scope_type,
            scope_id=scope_id,
            username=username,
            day=day.strftime("%Y%m%d"),
        )

    def replace_today(
        self,
        *,
        scope_type: str,
        scope_id: str,
        username: str,
        counts: dict[str, int],
        window_days: int,
    ) -> None:
        """原子重建当天桶；单桶容量按 STORE_LIMIT 截断（防单日异常刷量撑爆内存）。"""

        pipeline = self.redis_client.pipeline()
        key = self.build_bucket_key(scope_type, scope_id, username, timezone.localdate())
        pipeline.delete(key)
        top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[
            : max(1, settings.AI_ASSISTANT_COMMON_QUERY_STORE_LIMIT)
        ]
        if top:
            pipeline.zadd(key, {query_text: float(count) for query_text, count in top})
            # 窗口 + 2 天余量：统计窗口外的桶由 Redis 自动过期，零维护成本
            pipeline.expire(key, (window_days + 2) * 86400)
        pipeline.execute()

    def list_top(
        self,
        *,
        scope_type: str,
        scope_id: str,
        username: str,
        window_days: int,
        limit: int,
    ) -> list[CommonQuerySchema]:
        """读取统计窗口内天桶，按线性时间衰减加权合并返回 top K。

        权重：今天 1.0，i 天前 (window - i) / window（线性衰减）；
        Redis 异常降级为空列表（次要功能不阻断主流程）。
        """

        try:
            pipeline = self.redis_client.pipeline()
            weights: list[float] = []
            for offset in range(window_days):
                day = timezone.localdate() - timedelta(days=offset)
                weight = (window_days - offset) / window_days
                pipeline.zrange(
                    self.build_bucket_key(scope_type, scope_id, username, day),
                    0,
                    -1,
                    withscores=True,
                )
                weights.append(weight)
            merged: dict[str, float] = {}
            for weight, members in zip(weights, pipeline.execute()):
                for query_text, count in members:
                    merged[query_text] = merged.get(query_text, 0.0) + float(count) * weight
            top = sorted(merged.items(), key=lambda item: (-item[1], item[0]))[: max(0, limit)]
            return [CommonQuerySchema(query_text=query_text) for query_text, _score in top]
        except redis.RedisError:
            logger.exception(
                "[CommonQueryStore] redis read failed, scope_type=%s, scope_id=%s, username=%s",
                scope_type,
                scope_id,
                username,
            )
            return []


class OperationContextService:
    """为系统选择消息组装常见/历史操作上下文。"""

    @classmethod
    def build(
        cls,
        *,
        scope_type: str,
        scope_id: str,
        username: str,
    ) -> tuple[list[CommonQuerySchema], list[CommonQuerySchema]]:
        # 操作上下文总闸（设计稿已确认需求，默认开启；关闭时选择消息不携带常见/历史操作）
        if not getattr(settings, "AI_ASSISTANT_OPERATION_RANKING_ENABLED", True):
            return [], []
        common = cls.build_common(scope_type=scope_type, scope_id=scope_id, username=username)
        historical = cls.build_historical(scope_type=scope_type, scope_id=scope_id, username=username)
        return common, historical

    @classmethod
    def build_common(
        cls,
        *,
        scope_type: str,
        scope_id: str,
        username: str,
    ) -> list[CommonQuerySchema]:
        """读取当前用户在会话 scope 内的高频样例（窗口内线性时间衰减加权）。

        Redis 异常时降级为空列表（与历史行为一致，不阻断系统选择消息主流程）。
        """

        store = CommonQueryStore()
        return store.list_top(
            scope_type=scope_type,
            scope_id=scope_id,
            username=username,
            window_days=settings.AI_ASSISTANT_COMMON_QUERY_WINDOW_DAYS,
            limit=settings.AI_ASSISTANT_COMMON_QUERY_RETURN_LIMIT,
        )

    @classmethod
    def build_historical(
        cls,
        *,
        scope_type: str,
        scope_id: str,
        username: str,
    ) -> list[CommonQuerySchema]:
        """查询当前用户最近自然语言检索，先按会话 scope 过滤再去重。"""

        scan_limit = settings.AI_ASSISTANT_HISTORICAL_QUERY_SCAN_LIMIT
        return_limit = settings.AI_ASSISTANT_HISTORICAL_QUERY_LIMIT
        results: list[CommonQuerySchema] = []
        seen: set[str] = set()
        for query_text, _scope_type, _scope_id, _created_by in cls._iter_recent_queries(
            scan_limit,
            username=username,
            scope_type=scope_type,
            scope_id=scope_id,
        ):
            if query_text in seen:
                continue
            seen.add(query_text)
            results.append(CommonQuerySchema(query_text=query_text))
            if len(results) >= return_limit:
                break
        return results

    @classmethod
    def _iter_recent_queries(
        cls,
        scan_limit: int,
        username: str | None = None,
        since: datetime | None = None,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> Iterator[tuple[str, str, str, str]]:
        """迭代最近成功的 USER_INTENT 检索样例，产出 (query_text, scope_type, scope_id, created_by)。

        - 新 USER_INTENT：必须存在 SUCCESS 的来源 LOG_SEARCH；
          失败消息后续重试成功也能进入榜单，不依赖入口消息内的派生状态摘要
        - 历史 USER_INTENT：仍以 output_data.condition 非空识别成功检索
        - since：时间下界（常用操作刷新传"当天 0 点"，只迭代当天消息）
        - scope：历史操作传入，过滤条件在扫描上限之前生效；刷新任务不传 scope
        """

        filters = {
            "message_type": MessageType.USER_INTENT,
            "status": ExecutionStatus.SUCCESS,
        }
        if username:
            filters["created_by"] = username
        if since is not None:
            filters["created_at__gte"] = since
        if scope_type is not None:
            filters["conversation__scope_type"] = scope_type
        if scope_id is not None:
            filters["conversation__scope_id"] = scope_id
        messages = list(
            Message.objects.filter(**filters)
            .order_by("-id")
            .values_list(
                "id",
                "input_data",
                "output_data",
                "created_by",
                "conversation__scope_type",
                "conversation__scope_id",
            )[:scan_limit]
        )
        successful_intent_ids = set(
            Message.objects.filter(
                parent_message_id__in=[message_id for message_id, *_ in messages],
                message_type=MessageType.LOG_SEARCH,
                status=ExecutionStatus.SUCCESS,
            ).values_list("parent_message_id", flat=True)
        )
        for message_id, input_data, output_data, created_by, message_scope_type, message_scope_id in messages:
            query_text = (input_data or {}).get("query_text") or ""
            if not query_text:
                continue
            output = output_data if isinstance(output_data, dict) else {}
            is_new_protocol = "derived_messages" in output
            has_successful_search = message_id in successful_intent_ids
            has_legacy_condition = (
                not is_new_protocol and output.get("condition") is not None and bool(output.get("system_id"))
            )
            if not has_successful_search and not has_legacy_condition:
                continue
            yield query_text, message_scope_type, message_scope_id, created_by

    @classmethod
    def refresh_common_queries(cls) -> dict[str, int]:
        """定时任务入口：重建"当天"天桶（幂等），按用户 × Conversation scope 聚合检索频次。

        只扫当天消息（增量、量小，扫描上限兜底防异常刷量）；当天桶 delete+zadd
        原子替换，任务重投/重复执行不产生重复计数副作用；历史天的桶一经固化
        不再触碰，窗口外的由桶 TTL 自动清理（滑动窗口零维护成本）。
        """

        scan_limit = settings.AI_ASSISTANT_COMMON_QUERY_REFRESH_SCAN_LIMIT
        window_days = settings.AI_ASSISTANT_COMMON_QUERY_WINDOW_DAYS
        since = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        # (created_by, scope_type, scope_id) → {query_text: 当日次数}
        user_scope_counts: dict[tuple[str, str, str], dict[str, int]] = {}
        scanned = 0
        for query_text, scope_type, scope_id, created_by in cls._iter_recent_queries(scan_limit, since=since):
            scanned += 1
            counts = user_scope_counts.setdefault((created_by, scope_type, scope_id), {})
            counts[query_text] = counts.get(query_text, 0) + 1

        store = CommonQueryStore()
        refreshed = 0
        for (username, scope_type, scope_id), counts in user_scope_counts.items():
            try:
                store.replace_today(
                    scope_type=scope_type,
                    scope_id=scope_id,
                    username=username,
                    counts=counts,
                    window_days=window_days,
                )
                refreshed += 1
            except redis.RedisError:
                # 单组失败不影响其他组（次要功能，尽力而为）
                logger.exception(
                    "[OperationContextService] refresh common queries failed, scope_type=%s, scope_id=%s, username=%s",
                    scope_type,
                    scope_id,
                    username,
                )
        logger.info(
            "[OperationContextService] common queries refreshed, user_scopes=%d, scanned=%d",
            refreshed,
            scanned,
        )
        return {"refreshed_scopes": refreshed, "scanned_messages": scanned}
