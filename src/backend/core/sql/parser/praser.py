import numbers
from itertools import chain
from typing import Any, List, Optional, Set

import sqlglot
from sqlglot import exp

from core.sql.exceptions import SQLParseError
from core.sql.model import Table
from core.sql.parser.model import ParsedSQLInfo, SelectField, SqlVariable


class SqlQueryAnalysis:
    """
    封装了SQL查询的解析结果和相关操作。
    解析SQL，并将结果（引用的表、SQL变量、结果字段）存储为实例属性。
    提供了用实际值替换参数以生成完整SQL的方法。
    """

    original_sql: str
    dialect: Optional[str]

    referenced_tables: List[Table]
    sql_variables: List[SqlVariable]
    result_fields: List[SelectField]

    _parsed_expression: Optional[exp.Expression]  # Store the parsed AST

    def __init__(self, sql: str, dialect: Optional[str] = 'hive'):
        """
        初始化SQL查询分析器。此时不进行解析。
        """
        self.original_sql = sql
        self.dialect = dialect
        self.referenced_tables = []
        self.sql_variables = []
        self.result_fields = []
        self._parsed_expression = None  # Initialize as None

    def parse_sql(self):
        """
        使用sqlglot解析SQL并填充实例属性。
        如果已经解析过，则不会重复解析。
        """
        if self._parsed_expression is not None:  # 已解析
            return

        self.referenced_tables = []
        self.sql_variables = []
        self.result_fields = []

        if not self.original_sql or not self.original_sql.strip():
            return

        try:
            self._parsed_expression = sqlglot.parse_one(self.original_sql, read=self.dialect)
        except sqlglot.errors.ParseError as e:
            raise SQLParseError(f"SQL解析失败: {e}") from e

        # 1. 提取引用的表 (Extract referenced tables)
        cte_names = {cte.alias_or_name for cte in self._parsed_expression.find_all(exp.CTE)}
        for table_exp in self._parsed_expression.find_all(exp.Table):
            table_name = table_exp.name
            if table_name in cte_names:
                continue
            self.referenced_tables.append(Table(table_name=table_name))

        # 2. 提取SQL命名变量 (Extract SQL named variables)
        extracted_var_raw_names: Set[str] = set()
        for var_node in chain(
            self._parsed_expression.find_all(exp.Var), self._parsed_expression.find_all(exp.Placeholder)
        ):
            raw_name = var_node.name
            if raw_name == "?":
                raise SQLParseError("不支持匿名变量")
            elif raw_name not in extracted_var_raw_names:
                self.sql_variables.append(SqlVariable(raw_name=raw_name, display_name=raw_name))
                extracted_var_raw_names.add(raw_name)

        # 3. 提取查询结果字段 (Extract query result fields - SelectField)
        # 主要针对顶层的 SELECT 语句 (Mainly for top-level SELECT statements)
        current_expr = self._parsed_expression
        if isinstance(current_expr, exp.Union):
            raise SQLParseError("暂不支持Union查询。")
        if isinstance(current_expr, exp.Query) and current_expr.this:
            current_expr = current_expr.this

        select_to_inspect: Optional[exp.Select] = None
        if isinstance(current_expr, exp.Select):
            select_to_inspect = current_expr

        if select_to_inspect:
            for projection in select_to_inspect.expressions:
                display_name = projection.alias_or_name

                raw_name = display_name
                core_expression = projection.this if isinstance(projection, exp.Alias) else projection

                if isinstance(core_expression, exp.Column):
                    raw_name = core_expression.name

                self.result_fields.append(
                    SelectField(
                        display_name=display_name,
                        raw_name=raw_name,
                    )
                )

    def _create_sqlglot_literal(self, value: Any) -> exp.Expression:
        """
        将Python值转换为sqlglot的Literal表达式。
        """
        if isinstance(value, str):
            return exp.Literal.string(value)
        if isinstance(value, bool):
            return exp.Boolean(this=value)
        if isinstance(value, numbers.Integral):
            return exp.Literal.number(int(value))
        if isinstance(value, numbers.Real):
            return exp.Literal.number(float(value))
        if value is None:
            return exp.Null()
        raise TypeError(f"不支持将 Python 类型 '{type(value).__name__}' 自动转换为 SQL 字面量。值为: {value!r}")

    def _parameter_replacer_visitor(
        self, node: exp.Expression, named_params_dict: dict, dialect_str: Optional[str]
    ) -> exp.Expression:
        """
        用于sqlglot的transform方法的访问者函数。
        将exp.Var节点替换为named_params_dict中对应的字面量值。
        """
        if isinstance(node, (exp.Var, exp.Placeholder)):
            param_key = node.name
            if param_key == "?":
                raise SQLParseError("不支持匿名变量")
            if param_key in named_params_dict:
                return self._create_sqlglot_literal(named_params_dict[param_key])
            raise SQLParseError(f"参数 '{param_key}' 的值未在 params 字典中提供.")
        return node

    def generate_sql_with_values(
        self,
        params: dict,
        sql_template: Optional[str] = None,
        template_dialect: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        with_count: bool = False,
    ) -> dict:
        """使用 sqlglot 将 SQL 模板中的命名参数替换为实际值。

        - ``limit`` 和 ``offset`` 参数用于在生成的 SQL 中添加分页语句；
        - ``with_count`` 为 ``True`` 时同时返回统计总量的 SQL。
        """
        target_sql = sql_template if sql_template is not None else self.original_sql
        target_dialect = template_dialect if template_dialect is not None else self.dialect

        try:
            parsed_tree = sqlglot.parse_one(target_sql, read=target_dialect)
        except sqlglot.errors.ParseError as e:
            raise SQLParseError(f"SQL 模板解析失败 (SQL template parsing failed): {target_sql} - {e}") from e

        transformed_tree = parsed_tree.transform(self._parameter_replacer_visitor, params, target_dialect, copy=True)

        count_sql = None
        if with_count:
            count_expr = exp.select(exp.func("COUNT", exp.Star()).as_("count")).from_(
                transformed_tree.copy().subquery("_sub")
            )
            count_sql = count_expr.sql(dialect=target_dialect)

        if limit is not None:
            transformed_tree = transformed_tree.limit(limit)
        if offset:
            transformed_tree = transformed_tree.offset(offset)

        data_sql = transformed_tree.sql(dialect=target_dialect)

        return {"data": data_sql, "count": count_sql}

    def get_parsed_def(self) -> ParsedSQLInfo:
        """
        返回一个包含解析结果摘要的 Pydantic 模型实例，方便查看。
        确保在调用此方法前已调用 parse_sql()。
        """
        if self._parsed_expression is None and (self.original_sql and self.original_sql.strip()):
            self.parse_sql()
        return ParsedSQLInfo(
            original_sql=self.original_sql,
            dialect=self.dialect,
            referenced_tables=self.referenced_tables,
            sql_variables=self.sql_variables,
            result_fields=self.result_fields,
        )

    def regenerate_sql_from_ast(self, dialect: Optional[str] = None) -> Optional[str]:
        """
        从内部存储的AST重新生成SQL语句。主要用于测试或规范化SQL。
        确保在调用此方法前已调用 parse_sql。
        """
        if self._parsed_expression:
            return self._parsed_expression.sql(dialect=dialect or self.dialect)
        if self.original_sql and self.original_sql.strip():
            temp_expr = sqlglot.parse_one(self.original_sql, read=self.dialect)
            return temp_expr.sql(dialect=dialect or self.dialect)
        return None
