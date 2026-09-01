"""日志工具查询前置上下文：显式鉴权、DRF 校验和服务端表解析。"""

from dataclasses import dataclass
from typing import Any, Tuple

from rest_framework.exceptions import ValidationError as DrfValidationError

from apps.meta.models import System
from apps.meta.permissions import SearchLogPermission
from core.exceptions import ValidationError as CoreValidationError
from core.sql.constants import FieldType
from services.web.databus.models import CollectorPlugin
from services.web.query.ai_assistant.exceptions import (
    InvalidLogCondition,
    LogQueryFailed,
)
from services.web.query.ai_assistant.schemas import Condition, SearchCondition
from services.web.query.constants import DEFAULT_COLLECTOR_SORT_LIST
from services.web.query.serializers import CollectorSearchAllReqSerializer
from services.web.query.utils.search_config import QueryConditionOperator


@dataclass(frozen=True, slots=True)
class LogQueryContext:
    """已完成授权和条件注入、但尚未执行查询的不可变上下文。"""

    username: str
    namespace: str
    # 用户条件已按 Collector 规范化；敏感权限判断必须与实际 SQL 使用同一路径。
    condition: SearchCondition
    table: str
    conditions: Tuple[dict[str, Any], ...]


class LogQueryContextService:
    """为日志工具构造完成鉴权、条件标准化和表解析的查询上下文。

    ``scope_id`` 是权限和数据范围，不是用户 conditions 的普通字段。服务必须把它转换为
    首条 ``system_id`` 条件，防止共享采集表上的查询越出已授权系统。
    """

    @classmethod
    def build(cls, *, username: str, namespace: str, condition: SearchCondition) -> LogQueryContext:
        """按鉴权、条件校验、范围注入的固定顺序构造查询上下文。"""

        context_condition = condition.model_copy(deep=True)
        # 鉴权必须先于序列化，避免向无权用户暴露字段或时间校验细节。
        if not SearchLogPermission.has_system_search_permission(context_condition.scope_id, username):
            SearchLogPermission.raise_system_view_permission_exception(username=username)

        try:
            belongs_to_namespace = System.objects.filter(
                system_id=context_condition.scope_id,
                namespace=namespace,
            ).exists()
        except Exception as err:  # noqa: BLE001 - 本地元数据基础设施异常不得伪装成参数错误。
            raise LogQueryFailed() from err
        if not belongs_to_namespace:
            raise InvalidLogCondition()

        validated = cls._validate_condition(condition=context_condition, namespace=namespace)
        # Collector 会移除非 JSON 字段的 keys，并在前面加入时间条件；JSON key 保留原文。
        # 只取原用户条件对应的尾部，避免把平台注入的时间/系统字段当作用户查询字段。
        condition_count = len(context_condition.conditions)
        context_condition.conditions = (
            [Condition.model_validate(item) for item in validated["conditions"][-condition_count:]]
            if condition_count
            else []
        )
        # CollectorSearchAllReqSerializer 不注入权限条件，因此不能直接使用 validated["conditions"]。
        # 一期 scope 固定为单系统；首段权限判断已包含系统直权和场景间接授权。
        conditions = (cls._system_condition([str(context_condition.scope_id)]), *validated["conditions"])
        try:
            table = CollectorPlugin.build_collector_rt(namespace)
        except Exception as err:  # noqa: BLE001 - 表解析依赖异常统一收敛为脱敏领域错误。
            raise LogQueryFailed() from err

        return LogQueryContext(
            username=username,
            namespace=namespace,
            condition=context_condition,
            table=table,
            conditions=conditions,
        )

    @classmethod
    def _validate_condition(cls, *, condition: SearchCondition, namespace: str) -> dict:
        """复用日志检索 DRF 协议，将 Pydantic 条件标准化为现有查询结构。"""

        payload = {
            "namespace": namespace,
            "start_time": condition.start_time,
            "end_time": condition.end_time,
            "conditions": [item.model_dump() for item in condition.conditions],
            "page": 1,
            "page_size": 1,
            "sort_list": DEFAULT_COLLECTOR_SORT_LIST,
            "bind_system_info": False,
        }
        serializer = CollectorSearchAllReqSerializer(data=payload)
        # DRF 为每个实例复制字段；仅此工具入口保留 JSON key 原文，不改变 Web 的历史校验行为。
        # 必须在校验前设置，使权限检查和 SQL 构造使用同一条路径，而不是事后恢复未经校验的输入。
        key_field = serializer.fields["conditions"].child.fields["field"].fields["keys"].child
        key_field.trim_whitespace = False
        try:
            serializer.is_valid(raise_exception=True)
        except (DrfValidationError, CoreValidationError) as err:
            raise InvalidLogCondition() from err
        return serializer.validated_data

    @staticmethod
    def _system_condition(authorized_systems: list[str]) -> dict:
        """把已鉴权系统转换为共享采集表上的强制数据范围。"""

        return {
            "field": {"raw_name": "system_id", "field_type": FieldType.STRING.value, "keys": []},
            "operator": QueryConditionOperator.INCLUDE.value,
            "filters": authorized_systems,
        }
