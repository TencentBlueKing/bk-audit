from django.db import transaction

from core.utils.data import unique_id
from services.web.tool.constants import (
    BkvisionConfig,
    DataSearchConfigTypeEnum,
    SQLDataSearchConfig,
    ToolTypeEnum,
)
from services.web.tool.models import BkvisionToolConfig, DataSearchToolConfig, Tool
from services.web.vision.handlers.query import VisionHandler
from services.web.vision.models import Scenario, VisionPanel


@transaction.atomic
def create_tool_with_config(validated_data: dict) -> Tool:
    """
    创建工具实例，并根据类型写入相应的配置表
    """
    config_data = validated_data.get("config")

    tool = Tool.objects.create(**validated_data)

    if tool.tool_type == ToolTypeEnum.DATA_SEARCH.value:
        _create_sql_tool(tool, config_data)
    elif tool.tool_type == ToolTypeEnum.BK_VISION.value:
        _create_bkvision_tool(tool, config_data)

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
