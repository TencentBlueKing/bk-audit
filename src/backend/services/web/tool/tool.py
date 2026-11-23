import datetime
import time
from collections import defaultdict
from typing import Dict, Iterable, List, Set

import redis
from django.conf import settings
from django.db import transaction

from apps.meta.handlers.tag_binding import sync_resource_tags
from core.utils.data import unique_id
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy, StrategyTool
from services.web.tool.constants import (
    BkVisionConfig,
    DataSearchConfigTypeEnum,
    SQLDataSearchConfig,
    ToolTypeEnum,
)
from services.web.tool.exceptions import DataSearchSimpleModeNotSupportedError
from services.web.tool.models import (
    BkVisionToolConfig,
    DataSearchToolConfig,
    Tool,
    ToolTag,
)
from services.web.vision.handlers.query import VisionHandler
from services.web.vision.models import Scenario, VisionPanel


@transaction.atomic
def create_tool_with_config(validated_data: dict) -> Tool:
    """
    创建工具实例，并根据类型写入相应的配置表
    """
    config_data = validated_data.get("config")
    tag_names = validated_data.pop("tags", [])
    data_search_config_type = validated_data.pop("data_search_config_type", "")
    updated_time = validated_data.pop("updated_time", None)
    tool = Tool.objects.create(**validated_data)
    if tool.tool_type == ToolTypeEnum.DATA_SEARCH.value:
        if data_search_config_type == DataSearchConfigTypeEnum.SIMPLE:
            raise DataSearchSimpleModeNotSupportedError()
        _create_sql_tool(tool, config_data, data_search_config_type)
    elif tool.tool_type == ToolTypeEnum.BK_VISION.value:
        _create_bkvision_tool(tool, config_data, updated_time)
    sync_resource_tags(
        resource_uid=tool.uid,
        tag_names=tag_names,
        relation_model=ToolTag,
        relation_resource_field="tool_uid",
    )

    return tool


@transaction.atomic
def _create_sql_tool(tool: Tool, config_data: dict, config_type: str):
    """
    创建sql类型工具的子表配置
    """
    config = SQLDataSearchConfig(**config_data)
    DataSearchToolConfig.objects.create(
        tool=tool,
        data_search_config_type=config_type,
        sql=config.sql,
    )


@transaction.atomic
def _create_bkvision_tool(tool: Tool, config_data: dict, updated_time: datetime):
    """
    创建 bkvision 类型工具的子表配置
    """
    config = BkVisionConfig(**config_data)
    uid = config.uid
    panel, created = VisionPanel.objects.get_or_create(
        name=f"Tool-{tool.uid}",
        vision_id=uid,
        scenario=Scenario.TOOL,
        handler=VisionHandler.__name__,
        defaults={"id": unique_id(), "name": f"Tool-{tool.uid}"},
    )
    BkVisionToolConfig.objects.create(tool=tool, panel=panel, updated_time=updated_time)


def get_blocking_strategy_names(tool_uid: str) -> List[str]:
    """
    获取引用该工具且会阻塞停用/删除的策略名列表，返回空列表表示允许操作

    任意策略（全局或场景）引用该工具均会阻塞；草稿与已删除的策略不计入
    """

    strategy_ids = set(
        StrategyTool.objects.filter(tool_uid=str(tool_uid), strategy__is_deleted=False)
        .exclude(strategy__status=StrategyStatusChoices.DRAFT.value)
        .values_list("strategy_id", flat=True)
    )
    if not strategy_ids:
        return []
    return [
        strategy_name
        for _, strategy_name in Strategy.objects.filter(strategy_id__in=strategy_ids, is_deleted=False)
        .order_by("strategy_id")
        .values_list("strategy_id", "strategy_name")
    ]


def attach_strategy_refs(tools: Iterable[Tool]) -> None:
    """
    批量回填工具的策略引用信息，供列表与详情接口输出

    回填属性：
    - strategy_refs：阻塞停用/删除的策略列表 [{"strategy_id": int, "strategy_name": str}]
    - can_disable：是否允许停用
    - can_delete：是否允许删除
    """

    tool_list = list(tools)
    if not tool_list:
        return
    tool_uids = [str(tool.uid) for tool in tool_list]
    tool_strategy_ids: Dict[str, Set[int]] = defaultdict(set)
    for tool_uid, strategy_id in (
        StrategyTool.objects.filter(tool_uid__in=tool_uids, strategy__is_deleted=False)
        .exclude(strategy__status=StrategyStatusChoices.DRAFT.value)
        .values_list("tool_uid", "strategy_id")
        .distinct()
    ):
        tool_strategy_ids[str(tool_uid)].add(strategy_id)
    all_strategy_ids = {strategy_id for ids in tool_strategy_ids.values() for strategy_id in ids}
    name_map: Dict[int, str] = {}
    if all_strategy_ids:
        name_map = dict(
            Strategy.objects.filter(strategy_id__in=all_strategy_ids, is_deleted=False).values_list(
                "strategy_id", "strategy_name"
            )
        )
    for tool in tool_list:
        refs = [
            {"strategy_id": sid, "strategy_name": name_map.get(sid, "")}
            for sid in sorted(tool_strategy_ids.get(str(tool.uid), set()))
        ]
        setattr(tool, "strategy_refs", refs)
        # 被策略引用不影响停用（关展示不影响下钻）；仅删除受引用限制
        setattr(tool, "can_disable", True)
        setattr(tool, "can_delete", not refs)


class RecentToolUsageManager:
    """最近使用记录（按人隔离）

    产品口径：广场点击/执行参与排序；风险下钻/MCP/接口记录但不参与广场排序。
    - tool:recently_used:{username}：广场行为（参与排序）
    - tool:recently_used_other:{username}：下钻/MCP/接口行为（仅记录，不排序）
    """

    REDIS_KEY_TEMPLATE = "tool:recently_used:{username}"
    OTHER_KEY_TEMPLATE = "tool:recently_used_other:{username}"

    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            db=int(settings.REDIS_DB),
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )

    def _build_key(self, username: str) -> str:
        return self.REDIS_KEY_TEMPLATE.format(username=username)

    def _build_other_key(self, username: str) -> str:
        return self.OTHER_KEY_TEMPLATE.format(username=username)

    def record_usage(self, username: str, tool_uid: str, for_square: bool = True):
        """记录使用；for_square=True 广场行为（参与排序），False 下钻/MCP/接口（仅记录）"""
        if not username or not tool_uid:
            return

        key = self._build_key(username) if for_square else self._build_other_key(username)
        score = int(time.time())
        cutoff = score - settings.RECENT_USED_TTL
        self.redis_client.zremrangebyscore(key, '-inf', cutoff)
        self.redis_client.zadd(key, {tool_uid: score})
        self.redis_client.expire(key, settings.RECENT_USED_TTL)

    def get_recent_uids(self, username: str):
        """广场最近使用（按时间倒序），用于广场默认排序"""
        key = self._build_key(username)
        return self.redis_client.zrevrange(key, 0, -1)

    def get_recent_scores(self, username: str) -> dict:
        """广场最近使用 uid -> 最近使用时间戳，用于按时间倒序排序"""
        key = self._build_key(username)
        return dict(self.redis_client.zrange(key, 0, -1, withscores=True))

    def get_all_recent_uids(self, username: str):
        """全部最近使用（广场 + 下钻/MCP/接口合并，按时间倒序），用于最近使用标签与计数"""
        scores = {}
        for key in (self._build_key(username), self._build_other_key(username)):
            for uid, ts in self.redis_client.zrange(key, 0, -1, withscores=True):
                scores[uid] = max(scores.get(uid, 0), ts)
        return [uid for uid, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]


recent_tool_usage_manager = RecentToolUsageManager()
