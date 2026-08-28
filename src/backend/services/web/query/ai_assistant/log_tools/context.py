"""日志工具查询前置上下文：显式鉴权、DRF 校验和服务端表解析。"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Tuple

from rest_framework.exceptions import ValidationError as DrfValidationError

from apps.meta.permissions import SearchLogPermission
from core.exceptions import ValidationError as CoreValidationError
from core.sql.constants import FieldType
from core.utils.time import parse_datetime
from services.web.databus.models import CollectorPlugin
from services.web.query.ai_assistant.exceptions import InvalidLogCondition
from services.web.query.ai_assistant.schemas import SearchCondition
from services.web.query.constants import DEFAULT_COLLECTOR_SORT_LIST
from services.web.query.serializers import CollectorSearchAllReqSerializer
from services.web.query.utils.search_config import QueryConditionOperator


@dataclass(frozen=True, slots=True)
class LogQueryContext:
    """已完成授权和条件注入、但尚未执行查询的不可变上下文。"""

    username: str
    namespace: str
    condition: SearchCondition
    table: str
    conditions: Tuple[dict[str, Any], ...]


class LogQueryContextService:
    """为后续日志工具构造唯一的严格查询入口。"""

    @classmethod
    def build(cls, *, username: str, namespace: str, condition: SearchCondition) -> LogQueryContext:
        context_condition = condition.model_copy(deep=True)
        # 鉴权必须先于序列化，避免向无权用户暴露字段或时间校验细节。
        if not SearchLogPermission.has_system_search_permission(context_condition.scope_id, username):
            SearchLogPermission.raise_system_view_permission_exception(username=username)

        validated = cls._validate_condition(condition=context_condition, namespace=namespace)
        # 一期 scope 固定为单系统；首段权限判断已包含系统直权和场景间接授权。
        conditions = (cls._system_condition([str(context_condition.scope_id)]), *deepcopy(validated["conditions"]))
        return LogQueryContext(
            username=username,
            namespace=namespace,
            condition=context_condition,
            table=CollectorPlugin.build_collector_rt(namespace),
            conditions=conditions,
        )

    @classmethod
    def _validate_condition(cls, *, condition: SearchCondition, namespace: str) -> dict:
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
        try:
            serializer.is_valid(raise_exception=True)
            if parse_datetime(condition.start_time) > parse_datetime(condition.end_time):
                raise ValueError("start_time exceeds end_time")
        except (DrfValidationError, CoreValidationError, ValueError) as err:
            raise InvalidLogCondition() from err
        return serializer.validated_data

    @staticmethod
    def _system_condition(authorized_systems: list[str]) -> dict:
        return {
            "field": {"raw_name": "system_id", "field_type": FieldType.STRING.value, "keys": []},
            "operator": QueryConditionOperator.INCLUDE.value,
            "filters": authorized_systems,
        }
