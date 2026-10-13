"""Doris 原生标量读取和数值类别规范化。

JSON 类型与值分别读取，整数先在 LARGEINT 域守卫；DOUBLE 必须文本往返。
固定内部别名隔离业务路径，复用现有 JSONPath/SQL 双层转义。
"""
from dataclasses import dataclass

from pypika.terms import ValueWrapper

from core.sql.builder.terms import DorisJsonTypeExtractFunction
from services.web.query.ai_assistant.log_tools.schemas import (
    AGGREGATION_STANDARD_FIELD_TYPES,
    LogFieldRef,
)

JSON_NUMBER_REGEXP = r"^-?(0|[1-9][0-9]*)([.][0-9]+)?([eE][+-]?[0-9]+)?$"
INTEGER_KINDS = "('int','bigint','largeint','tinyint','smallint')"
FLOAT_KINDS = "('double','float')"
SCALAR_KINDS = "('int','bigint','largeint','tinyint','smallint','double','float','string','bool','boolean')"


def literal(value: str) -> str:
    """编码普通 Doris 字符串；JSONPath 已经处理过反斜杠时使用其专用构造。"""
    return ValueWrapper(value.replace("\\", "\\\\")).get_sql()


@dataclass(frozen=True)
class StatisticsFieldSQL:
    """每个唯一业务字段在各规范化 CTE 中的受控表达式。"""

    field: LogFieldRef
    index: int

    @property
    def prefix(self):
        """返回与调用方 ID 无关的内部别名。"""
        return f"f{self.index}"

    def source_columns(self, builder) -> list[str]:
        """从原列直接读取类型及整数/浮点/文本，禁止先用显示文本重建数字。"""
        p = self.prefix
        root = builder.get_pypika_field(self.field.raw_name).get_sql(quote_char="`")
        if self.field.keys:
            path = DorisJsonTypeExtractFunction.json_path_term(self.field.keys).get_sql()
            # BKBase 的 JSON 函数也支持 VARIANT；按路径读取实际类型，
            # 不依赖高版本 VARIANT_TYPE，也避免 VARIANT 布尔 CAST 变成 0/1。
            kind = f"LOWER(JSON_TYPE({root},{path}))"
            integer = f"CASE WHEN {kind} IN {INTEGER_KINDS} THEN JSON_EXTRACT_LARGEINT({root},{path}) END"
            double = f"CASE WHEN {kind} IN {FLOAT_KINDS} THEN JSON_EXTRACT_DOUBLE({root},{path}) END"
            text = f"JSON_EXTRACT_STRING({root},{path})"
            # boolean 使用 JSON 原生文本，避免 VARIANT 直接 CAST 的 0/1 表示。
            text = (
                f"CASE WHEN {kind} IN ('bool','boolean') THEN CAST(JSON_EXTRACT({root},{path}) AS STRING) "
                f"ELSE {text} END"
            )
        else:
            declared = AGGREGATION_STANDARD_FIELD_TYPES.get(self.field.raw_name)
            if declared in {"int", "long", "timestamp"}:
                kind = f"CASE WHEN {root} IS NOT NULL THEN 'bigint' END"
                integer, double, text = f"CAST({root} AS LARGEINT)", "NULL", "NULL"
            elif declared in {"float", "double"}:
                kind = f"CASE WHEN {root} IS NOT NULL THEN 'double' END"
                integer, double, text = "NULL", f"CAST({root} AS DOUBLE)", "NULL"
            else:
                kind = f"CASE WHEN {root} IS NOT NULL THEN 'string' END"
                integer, double, text = "NULL", "NULL", f"CAST({root} AS STRING)"
        return [f"{kind} AS {p}_observed", f"{integer} AS {p}_i_raw", f"{double} AS {p}_d_raw", f"{text} AS {p}_text"]

    def safe_columns(self) -> list[str]:
        """范围先转为 NULL，防止超界数字进入后续 CAST。"""
        p = self.prefix
        return [
            f"CASE WHEN {p}_i_raw BETWEEN CAST(-9007199254740991 AS LARGEINT) "
            f"AND CAST(9007199254740991 AS LARGEINT) THEN {p}_i_raw END AS {p}_i_safe",
            f"CASE WHEN {p}_d_raw BETWEEN CAST('-9007199254740991' AS DOUBLE) "
            f"AND CAST('9007199254740991' AS DOUBLE) THEN {p}_d_raw END AS {p}_d_safe",
        ]

    def text_columns(self) -> list[str]:
        """只对安全 DOUBLE 产生整数候选和统一文本候选。"""
        p = self.prefix
        return [f"CAST({p}_d_safe AS BIGINT) AS {p}_d_integer", f"CAST({p}_d_safe AS STRING) AS {p}_d_text"]

    def canonical_columns(self) -> list[str]:
        """生成 typed 键，数字整值统一为整数文本，空字符串原样保留。"""
        p = self.prefix
        number = (
            f"CASE WHEN {p}_observed IN {INTEGER_KINDS} THEN CAST({p}_i_safe AS STRING) "
            f"WHEN {p}_d_safe = CAST({p}_d_integer AS DOUBLE) THEN CAST({p}_d_integer AS STRING) "
            f"WHEN {p}_d_text REGEXP {literal(JSON_NUMBER_REGEXP)} AND CAST({p}_d_text AS DOUBLE) = {p}_d_safe "
            f"THEN {p}_d_text END"
        )
        kind = (
            f"CASE WHEN {p}_observed IS NULL OR {p}_observed = 'null' THEN NULL "
            f"WHEN {p}_observed IN {INTEGER_KINDS} OR {p}_observed IN {FLOAT_KINDS} THEN 'number' "
            f"WHEN {p}_observed IN ('bool','boolean') THEN 'boolean' ELSE {p}_observed END"
        )
        key = (
            f"CASE WHEN {p}_observed IN {INTEGER_KINDS} OR {p}_observed IN {FLOAT_KINDS} "
            f"THEN {number} ELSE {p}_text END"
        )
        return [f"{kind} AS {p}_type", f"{key} AS {p}_key"]
