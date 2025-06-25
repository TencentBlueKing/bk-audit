from typing import List, Type

from bk_resource import resource
from django.db import models, transaction

from core.utils.data import unique_id
from services.web.tool.constants import (
    BkvisionConfig,
    DataSearchConfigTypeEnum,
    SQLDataSearchConfig,
    ToolTypeEnum,
)
from services.web.tool.models import (
    BkvisionToolConfig,
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

    tool = Tool.objects.create(**validated_data)
    if tool.tool_type == ToolTypeEnum.DATA_SEARCH.value:
        _create_sql_tool(tool, config_data)
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
def _create_sql_tool(tool: Tool, config_data: dict):
    """
    创建sql类型工具的子表配置
    """
    config = SQLDataSearchConfig(**config_data)
    DataSearchToolConfig.objects.create(
        tool=tool,
        data_search_config_type=DataSearchConfigTypeEnum.SQL,
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
    BkvisionToolConfig.objects.create(tool=tool, panel=panel)


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
