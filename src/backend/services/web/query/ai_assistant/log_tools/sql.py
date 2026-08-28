"""基于已验证字段引用的日志投影 SQL 构建器。"""

from typing import Sequence

from pypika.functions import Count

from services.web.query.ai_assistant.log_tools.schemas import LogFieldRef
from services.web.query.utils.doris import BaseDorisSQLBuilder


class ProjectedLogSQLBuilder(BaseDorisSQLBuilder):
    """只生成显式字段投影，禁止退化为 SELECT *。"""

    def build_data_sql(self, fields: Sequence[LogFieldRef]) -> str:
        if not fields:
            raise ValueError("at least one projected field is required")

        validated_fields = []
        for field in fields:
            if not isinstance(field, LogFieldRef):
                raise TypeError("fields must be LogFieldRef instances")
            # model_construct 可绕过 Pydantic 校验，进入 SQL 层前重新验证安全边界。
            validated_fields.append(LogFieldRef.model_validate(field.model_dump()))

        terms = [self.get_pypika_field(field.raw_name, field.keys) for field in validated_fields]
        query = self._build_order_by(self._build_where(self.query.select(*terms)))
        return str(query.limit(self.page_size).offset(self.page_size * (self.page - 1)))

    def build_count_sql(self) -> str:
        """基于与数据查询相同的已验证条件统计总数。"""

        return str(self._build_where(self.query).select(Count("*").as_("count")).limit(1))
