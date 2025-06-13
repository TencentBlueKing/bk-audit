from typing import List, Optional

from pydantic import BaseModel
from pydantic import Field as PydanticField

from core.sql.model import Table


class SqlVariable(BaseModel):
    """
    SQL 中的变量（参数）信息
    """

    raw_name: str = PydanticField(..., description="SQL中原始变量名 (例如 :user_id, @status, ${department})")
    description: Optional[str] = PydanticField(None, description="变量的详细描述")
    required: bool = PydanticField(True, description="该变量是否为必填项")
    display_name: str = PydanticField(None, description="用户定义的显示名称")


class SelectField(BaseModel):
    """
    SQL 查询结果中的字段信息 (即 SELECT 列表中的项)
    """

    display_name: str = PydanticField(..., description="查询结果中字段的最终名称（SQL SELECT子句中的列名或别名）")
    raw_name: Optional[str] = PydanticField(None, description="如果该字段直接来自表列，则为源表中的原始列名。对于表达式或字面量，此项为None。")


class ParsedSQLInfo(BaseModel):
    """
    Sql查询解析结果
    """

    original_sql: str
    dialect: Optional[str] = None
    referenced_tables: List[Table]
    sql_variables: List[SqlVariable]
    result_fields: List[SelectField]
