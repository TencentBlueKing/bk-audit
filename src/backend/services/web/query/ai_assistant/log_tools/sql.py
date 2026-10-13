"""受控日志投影与已知 JSON 父路径的样本查询。

字段发现仅投影根列及脱敏身份列，并在 Doris 过滤有效父对象。
完整统计构造器沿用原导入路径，统计范围不受样本查询影响。
"""
from typing import Sequence

from pypika.queries import QueryBuilder
from pypika.terms import Function

from core.sql.builder.terms import DorisJsonTypeExtractFunction
from services.web.query.ai_assistant.log_tools.schemas import LogFieldRef
from services.web.query.ai_assistant.log_tools.statistics_sql import (
    StatisticsSQLBuilder,
)
from services.web.query.utils.doris import BaseDorisSQLBuilder


class ProjectedLogSQLBuilder(BaseDorisSQLBuilder):
    """只生成显式字段投影，禁止退化为 SELECT *。"""

    def build_data_sql(self, fields: Sequence[LogFieldRef]) -> str:
        """根据受控投影、检索条件和排序构造分页明细 SQL。"""

        query = self._build_order_by(self._build_projected_query(fields))
        return str(query.limit(self.page_size).offset(self.page_size * (self.page - 1)))

    def _build_projected_query(self, fields: Sequence[LogFieldRef]) -> QueryBuilder:
        """统一复验投影字段并保留检索条件，供明细和父对象采样共用。"""

        if not fields:
            raise ValueError("at least one projected field is required")

        validated_fields = []
        for field in fields:
            if not isinstance(field, LogFieldRef):
                raise TypeError("fields must be LogFieldRef instances")
            # model_construct 可绕过 Pydantic 校验，进入 SQL 层前重新验证安全边界。
            validated_fields.append(LogFieldRef.model_validate(field.model_dump()))

        terms = [self.get_pypika_field(field.raw_name, field.keys) for field in validated_fields]
        return self._build_where(self.query.select(*terms))

    def build_parent_object_sample_sql(self, fields: Sequence[LogFieldRef], parent_field: LogFieldRef) -> str:
        """只从已知 JSON 父路径含子键的对象行中取样，保留完整根列供后续脱敏。"""

        if not isinstance(parent_field, LogFieldRef):
            raise TypeError("parent_field must be a LogFieldRef instance")
        parent_field = LogFieldRef.model_validate(parent_field.model_dump())
        if parent_field.raw_name not in self.JSON_TYPE_FIELDS:
            raise ValueError("parent sample requires a JSON column")
        root = self.get_pypika_field(parent_field.raw_name)
        path = DorisJsonTypeExtractFunction.json_path_term(parent_field.keys)
        parent_type = Function("JSON_TYPE", root, path)
        child_count = Function("ARRAY_SIZE", Function("JSON_KEYS", root, path))
        query = self._build_projected_query(fields).where(parent_type == "object").where(child_count > 0)
        return str(self._build_order_by(query).limit(self.page_size))


LogAggregationSQLBuilder = StatisticsSQLBuilder
