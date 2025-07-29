import numbers
from datetime import datetime
from itertools import chain
from typing import Any, List, Optional, Set

import sqlglot
from sqlglot import exp

from core.sql.exceptions import SQLParseError
from core.sql.model import Table
from core.sql.parser.model import (
    ParsedSQLInfo,
    RangeVariableData,
    SelectField,
    SqlVariable,
)

_SKIP_NULL_OPERATORS = {
    "eq": exp.EQ,
    "exact": exp.EQ,
    "gt": exp.GT,
    "gte": exp.GTE,
    "lt": exp.LT,
    "lte": exp.LTE,
    "like": exp.Like,
    "in": exp.In,
}


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
            if table_exp.db:
                table_name = table_exp.db
                storage = table_exp.name
            else:
                table_name = table_exp.name
                storage = None
            if table_name in cte_names:
                continue
            self.referenced_tables.append(Table(table_name=table_name, storage=storage))

        # 出现在 SKIP_NULL_CLAUSE 中的变量默认视为非必填
        skip_null_var_names = self.get_skip_null_var_names(self._parsed_expression)

        # 2. 提取SQL命名变量 (Extract SQL named variables)
        extracted_var_raw_names: Set[str] = set()
        for var_node in chain(
            self._parsed_expression.find_all(exp.Var), self._parsed_expression.find_all(exp.Placeholder)
        ):
            raw_name = var_node.name
            if raw_name == "?":
                raise SQLParseError(message="不支持匿名变量")
            elif raw_name not in extracted_var_raw_names:
                self.sql_variables.append(
                    SqlVariable(raw_name=raw_name, display_name=raw_name, required=raw_name not in skip_null_var_names)
                )
                extracted_var_raw_names.add(raw_name)

        # 3. 提取查询结果字段 (Extract query result fields - SelectField)
        # 主要针对顶层的 SELECT 语句 (Mainly for top-level SELECT statements)
        current_expr = self._parsed_expression
        if isinstance(current_expr, exp.Union):
            raise SQLParseError(message="暂不支持Union查询。")
        if isinstance(current_expr, exp.Query) and current_expr.this:
            current_expr = current_expr.this

        select_to_inspect: Optional[exp.Select] = None
        if isinstance(current_expr, exp.Select):
            select_to_inspect = current_expr

        if select_to_inspect:
            for projection in select_to_inspect.expressions:
                raw_name = projection.alias_or_name
                if not raw_name:
                    raise SQLParseError(message=f"查询结果字段 {projection} 缺少名称")
                if raw_name == "*":
                    raise SQLParseError(message="不支持查询结果字段为 *")

                self.result_fields.append(
                    SelectField(
                        display_name=raw_name,
                        raw_name=raw_name,
                    )
                )

    def get_skip_null_var_names(self, parsed_expression: exp.Expression):
        """获取 SKIP_NULL_CLAUSE 中的变量名"""
        skip_null_var_names: Set[str] = set()
        for func in parsed_expression.find_all(exp.Func):
            if func.name.upper() == "SKIP_NULL_CLAUSE" and len(func.expressions) >= 3:
                value_expr = func.expressions[2]
                for var_node in chain(value_expr.find_all(exp.Var), value_expr.find_all(exp.Placeholder)):
                    if var_node.name != "?":
                        skip_null_var_names.add(var_node.name)
        return skip_null_var_names

    def _create_sqlglot_literal(self, value: Any) -> exp.Expression:
        """
        将Python值转换为sqlglot的Literal表达式。
        """
        if isinstance(value, RangeVariableData):
            t = exp.Tuple(
                expressions=[
                    self._create_sqlglot_literal(value.start),
                    self._create_sqlglot_literal(value.end),
                ]
            )
            t.set("is_range", True)
            return t
        if isinstance(value, str):
            return exp.Literal.string(value)
        if isinstance(value, bool):
            return exp.Boolean(this=value)
        if isinstance(value, numbers.Integral):
            return exp.Literal.number(int(value))
        if isinstance(value, numbers.Real):
            return exp.Literal.number(float(value))
        if isinstance(value, list):
            return exp.Tuple(expressions=[self._create_sqlglot_literal(item) for item in value])
        if value is None:
            return exp.Null()
        raise TypeError(f"不支持将 Python 类型 '{type(value).__name__}' 自动转换为 SQL 字面量。值为: {value!r}")

    def _parameter_replacer_visitor(
        self, node: exp.Expression, named_params_dict: dict, dialect_str: Optional[str], skip_null_var_names: Set[str]
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
            elif param_key in skip_null_var_names:
                return self._create_sqlglot_literal(None)
            raise SQLParseError(f"参数 '{param_key}' 的值未在 params 字典中提供.")
        return node

    def _custom_function_visitor(
        self, node: exp.Expression, named_params_dict: dict, dialect_str: Optional[str]
    ) -> exp.Expression:
        """处理自定义函数，如 TIME_RANGE 和 SKIP_NULL_CLAUSE"""
        if isinstance(node, exp.Func):
            func_name = node.name.upper()
            if func_name == "TIME_RANGE":
                return self._replace_time_range(node)
            if func_name == "SKIP_NULL_CLAUSE":
                return self._replace_skip_null_clause(node)
        return node

    def _replace_time_range(self, node: exp.Func) -> exp.Expression:
        """将 TIME_RANGE 函数替换为实际的时间范围比较语句"""
        field, range_data, *extra = node.expressions
        if not (isinstance(range_data, exp.Tuple) and range_data.args.get('is_range', False)):
            raise SQLParseError("TIME_RANGE 函数的第二个参数类型必须是范围数组")
        fmt = None
        if extra and isinstance(extra[0], exp.Literal):
            fmt = extra[0].this

        start_val, end_val = range_data.expressions[0].this, range_data.expressions[1].this
        if fmt:
            if fmt == 'Timestamp(s)':  # 秒级时间戳
                start_val = int(start_val) // 1000
                end_val = int(end_val) // 1000
            elif fmt == 'Timestamp(ms)':  # 毫秒级时间戳(保持原样)
                start_val = int(start_val)
                end_val = int(end_val)
            elif fmt == 'Timestamp(us)':  # 微秒级时间戳
                start_val = int(start_val) * 1000
                end_val = int(end_val) * 1000
            else:  # 其他格式按原样处理
                start_val = datetime.fromtimestamp(int(start_val) / 1000).strftime(fmt)
                end_val = datetime.fromtimestamp(int(end_val) / 1000).strftime(fmt)
        else:
            start_val = int(start_val)
            end_val = int(end_val)
        low = self._create_sqlglot_literal(start_val)
        high = self._create_sqlglot_literal(end_val)
        return exp.And(
            this=exp.GTE(this=field.copy(), expression=low),
            expression=exp.LT(this=field.copy(), expression=high),
        )

    def _replace_skip_null_clause(self, node: exp.Func) -> exp.Expression:
        """将 SKIP_NULL_CLAUSE 函数替换为实际的条件语句"""
        if len(node.expressions) < 3:
            raise SQLParseError("SKIP_NULL_CLAUSE 参数不足")

        field_expr, op_expr, value_expr, *extra = node.expressions

        if isinstance(value_expr, exp.Null) or (isinstance(value_expr, exp.Tuple) and not value_expr.expressions):
            return exp.true()

        invert = False
        if extra:
            flag_expr = extra[0]
            if isinstance(flag_expr, exp.Boolean):
                invert = flag_expr.this

        op_name = op_expr.this if isinstance(op_expr, exp.Literal) else op_expr.name
        op_name = op_name.lower()

        op_cls = _SKIP_NULL_OPERATORS.get(op_name)
        if op_cls is None:
            raise SQLParseError(f"不支持的操作符: {op_name}")
        elif op_cls is exp.In:
            values = value_expr.expressions if isinstance(value_expr, exp.Tuple) else [value_expr]
            base_expr = op_cls(this=field_expr, expressions=values)
        else:
            base_expr = op_cls(this=field_expr, expression=value_expr)

        return exp.Not(this=base_expr) if invert else base_expr

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

        skip_null_var_names = self.get_skip_null_var_names(parsed_tree)

        transformed_tree = parsed_tree.transform(
            self._parameter_replacer_visitor, params, target_dialect, skip_null_var_names, copy=True
        )
        transformed_tree = transformed_tree.transform(self._custom_function_visitor, params, target_dialect, copy=True)

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
