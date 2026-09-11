"""常见/历史操作上下文（D3 定稿方案；常用操作已高频化改造）。

常见操作 = 当前用户的高频自然语言检索样例（"常用 = 高频"，产品确认）：
- 天桶 ZSet 计数（member=query_text 原文，score=当日出现次数），
  由 Celery 定时任务每小时重建"当天"桶（幂等，只扫当天消息，量小）；
- 读取时合并统计窗口内的天桶并按线性时间衰减加权（今天 1.0 → 窗口边缘 ~0.07），
  持续使用 > 集中突击 > 历史热点，防老操作永久霸榜；
- 桶 TTL = 窗口 + 2 天，Redis 自动滚动清理，内存有界；次要功能全链路降级安全
  （Redis 异常返回空列表，不阻断系统选择消息主流程）。
历史操作 = 当前用户最近的自然语言检索，直接查询消息表（按系统过滤），语义不变。

数据源覆盖 NATURAL_LANGUAGE_SEARCH 与 USER_INTENT（统一入口）两类消息：
意图消息仅收录真正产出检索条件的（output 携带 condition + system_id），
SYSTEM_REQUIRED / unrecognized 等引导性结果不进榜单。
"""

import logging
from datetime import date, datetime, timedelta
from typing import Iterable

import redis
from django.conf import settings
from django.utils import timezone

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas.audit_search import CommonQuerySchema

logger = logging.getLogger(__name__)

# v2：天桶 ZSet（与 v1 的无 TTL list 结构隔离；旧 key 不再读写，残留无害且量小）
COMMON_QUERY_BUCKET_KEY_TEMPLATE = "bk_audit:ai_assistant:common_queries_v2:{system_id}:{username}:d{day}"


def extract_system_ids(systems: Iterable[dict]) -> set[str]:
    """从系统选择快照的系统列表提取 system_id 集合（父消息 scope 校验与历史操作过滤共用）。"""

    return {system.get("system_id") for system in systems if system.get("system_id")}


class CommonQueryStore:
    """用户高频检索样例的天桶 ZSet 存储（资源受控 + 全链路降级安全的次要功能）。

    - 天桶：member=query_text 原文，score=当日出现次数；TTL=窗口+2 天自动滚动清理
    - 写：replace_today 原子重建当天桶（MULTI：delete+zadd+expire），幂等可重投
      （delete+rebuild 而非累加，任务重复执行不产生重复计数副作用）
    - 读：list_top 一次 pipeline 拉窗口内全部天桶（≤ 窗口×系统 个小 ZSet），
      Python 端线性衰减加权合并 top K——不依赖 Redis 6.2+ 的 ZUNION，
      无临时 key 残留风险；跨系统同句合并频次（多系统查过 = 更常用）
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
    def build_bucket_key(system_id: str, username: str, day: date) -> str:
        return COMMON_QUERY_BUCKET_KEY_TEMPLATE.format(
            system_id=system_id, username=username, day=day.strftime("%Y%m%d")
        )

    def replace_today(self, *, system_id: str, username: str, counts: dict[str, int], window_days: int) -> None:
        """原子重建当天桶；单桶容量按 STORE_LIMIT 截断（防单日异常刷量撑爆内存）。"""

        pipeline = self.redis_client.pipeline()
        key = self.build_bucket_key(system_id, username, timezone.localdate())
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
        self, *, system_ids: Iterable[str], username: str, window_days: int, limit: int
    ) -> list[CommonQuerySchema]:
        """读取统计窗口内天桶，按线性时间衰减加权合并返回 top K。

        权重：今天 1.0，i 天前 (window - i) / window（线性衰减）；
        Redis 异常降级为空列表（次要功能不阻断主流程）。
        """

        try:
            system_id_list = list(system_ids)
            pipeline = self.redis_client.pipeline()
            weights: list[float] = []
            for offset in range(window_days):
                day = timezone.localdate() - timedelta(days=offset)
                weight = (window_days - offset) / window_days
                for system_id in system_id_list:
                    pipeline.zrange(self.build_bucket_key(system_id, username, day), 0, -1, withscores=True)
                    weights.append(weight)
            merged: dict[str, float] = {}
            for weight, members in zip(weights, pipeline.execute()):
                for query_text, count in members:
                    merged[query_text] = merged.get(query_text, 0.0) + float(count) * weight
            top = sorted(merged.items(), key=lambda item: (-item[1], item[0]))[: max(0, limit)]
            return [CommonQuerySchema(query_text=query_text) for query_text, _score in top]
        except redis.RedisError:
            logger.exception(
                "[CommonQueryStore] redis read failed, system_ids=%s, username=%s", system_id_list, username
            )
            return []


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
        """读取当前用户在所选系统的高频样例（窗口内线性时间衰减加权，跨系统合并频次）。

        Redis 异常时降级为空列表（与历史行为一致，不阻断系统选择消息主流程）。
        """

        store = CommonQueryStore()
        return store.list_top(
            system_ids=system_ids,
            username=username,
            window_days=settings.AI_ASSISTANT_COMMON_QUERY_WINDOW_DAYS,
            limit=settings.AI_ASSISTANT_COMMON_QUERY_RETURN_LIMIT,
        )

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
    def _iter_recent_queries(cls, scan_limit: int, username: str | None = None, since: datetime | None = None):
        """迭代最近成功检索样例（NL + USER_INTENT 统一入口），产出 (query_text, system_ids, created_by)。

        - NL 消息：系统取 context_data.system_selection.systems
        - USER_INTENT：系统取 output_data.system_id；仅 condition 非空（真正产出检索并续链）
          才收录——SYSTEM_REQUIRED / unrecognized 等引导性输出不是检索，不进榜单
        - since：时间下界（常用操作刷新传"当天 0 点"，只迭代当天消息）
        """

        filters = {
            "message_type__in": [MessageType.NATURAL_LANGUAGE_SEARCH, MessageType.USER_INTENT],
            "status": ExecutionStatus.SUCCESS,
        }
        if username:
            filters["created_by"] = username
        if since is not None:
            filters["created_at__gte"] = since
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
        """定时任务入口：重建"当天"天桶（幂等），按用户 × 系统聚合当日检索频次。

        只扫当天消息（增量、量小，扫描上限兜底防异常刷量）；当天桶 delete+zadd
        原子替换，任务重投/重复执行不产生重复计数副作用；历史天的桶一经固化
        不再触碰，窗口外的由桶 TTL 自动清理（滑动窗口零维护成本）。
        """

        scan_limit = settings.AI_ASSISTANT_COMMON_QUERY_REFRESH_SCAN_LIMIT
        window_days = settings.AI_ASSISTANT_COMMON_QUERY_WINDOW_DAYS
        since = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        # (created_by, system_id) → {query_text: 当日次数}
        user_system_counts: dict[tuple[str, str], dict[str, int]] = {}
        scanned = 0
        for query_text, system_ids, created_by in cls._iter_recent_queries(scan_limit, since=since):
            scanned += 1
            for system_id in system_ids:
                counts = user_system_counts.setdefault((created_by, system_id), {})
                counts[query_text] = counts.get(query_text, 0) + 1

        store = CommonQueryStore()
        refreshed = 0
        for (username, system_id), counts in user_system_counts.items():
            try:
                store.replace_today(
                    system_id=system_id,
                    username=username,
                    counts=counts,
                    window_days=window_days,
                )
                refreshed += 1
            except redis.RedisError:
                # 单组失败不影响其他组（次要功能，尽力而为）
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
