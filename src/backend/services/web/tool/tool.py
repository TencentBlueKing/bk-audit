import time
from typing import List, Type

import redis
from bk_resource import resource
from django.conf import settings
from django.db import models, transaction
from django.db.models import QuerySet

from core.utils.data import unique_id
from services.web.tool.constants import (
    BkvisionConfig,
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
    data_search_config_type = validated_data.pop("data_search_config_type", None)
    tool = Tool.objects.create(**validated_data)
    if tool.tool_type == ToolTypeEnum.DATA_SEARCH.value:
        if data_search_config_type == DataSearchConfigTypeEnum.SIMPLE:
            raise DataSearchSimpleModeNotSupportedError()
        _create_sql_tool(tool, config_data, data_search_config_type)
    elif tool.tool_type == ToolTypeEnum.BK_VISION.value:
        _create_bkvision_tool(tool, config_data)
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
def _create_bkvision_tool(tool: Tool, config_data: dict):
    """
    创建 bkvision 类型工具的子表配置
    """
    config = BkvisionConfig(**config_data)
    uid = config.uid
    panel, created = VisionPanel.objects.get_or_create(
        vision_id=uid,
        scenario=Scenario.TOOL,
        handler=VisionHandler.__name__,
        defaults={
            "id": unique_id(),
        },
    )
    BkVisionToolConfig.objects.create(tool=tool, panel=panel)


def sync_resource_tags(
    relation_resource_field: str,
    resource_uid: str,
    tag_names: List[str],
    relation_model: Type[models.Model],
) -> None:
    """
    同步资源标签关联

    参数:
        relation_resource_field: 关联表中关联资源的字段名，
        resource_uid: 资源唯一标识
        tag_names: 标签名列表
        relation_model: 关联表模型类
    """
    with transaction.atomic():
        # 删除旧关联
        filter_kwargs = {relation_resource_field: resource_uid}
        relation_model.objects.filter(**filter_kwargs).delete()

        if not tag_names:
            return

        # 批量保存标签
        tags = resource.meta.save_tags([{"tag_name": t} for t in tag_names])

        # 批量创建关联
        objs = [relation_model(**{relation_resource_field: resource_uid, "tag_id": t["tag_id"]}) for t in tags]
        relation_model.objects.bulk_create(objs)


def custom_sort_order(
    queryset: QuerySet,
    ordering_field: str,
    value_list: List,
) -> QuerySet:
    """
    自定义排序 .

    :param queryset: 查询集
    :param ordering_field: 排序字段
    :param value_list: 排序字段排序值列表,从小到大
    """
    if not ordering_field:
        return queryset
    desc = False
    if ordering_field.startswith("-"):
        desc = True
        ordering_field = ordering_field[1:]

    clauses = " ".join(
        "WHEN {}='{}' THEN {} ".format(ordering_field, value if isinstance(value, int) else str(value), idx)
        for idx, value in enumerate(value_list)
    )
    ordering = "CASE %s END " % clauses

    if desc:
        queryset = queryset.extra(select={"ordering": ordering}, order_by=("-ordering",))
    else:
        queryset = queryset.extra(select={"ordering": ordering}, order_by=("ordering",))

    return queryset


class RecentToolUsageManager:
    REDIS_KEY_TEMPLATE = "tool:recently_used:{username}"

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

    def record_usage(self, username: str, tool_uid: str):
        if not username or not tool_uid:
            return

        key = self._build_key(username)
        score = int(time.time())
        cutoff = score - settings.RECENT_USED_TTL
        self.redis_client.zremrangebyscore(key, '-inf', cutoff)
        self.redis_client.zadd(key, {tool_uid: score})
        self.redis_client.expire(key, settings.RECENT_USED_TTL)

    def get_recent_uids(self, username: str):
        key = self._build_key(username)
        return self.redis_client.zrevrange(key, 0, -1)


recent_tool_usage_manager = RecentToolUsageManager()
