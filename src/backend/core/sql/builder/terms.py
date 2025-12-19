# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from typing import Any, Iterator, List, Optional, Union

from pymysql.converters import escape_string
from pypika.terms import Criterion
from pypika.terms import Field as _PypikaField
from pypika.terms import Function, NodeT
from pypika.utils import builder, format_alias_sql, format_quotes

from core.sql.constants import DORIS_FIELD_KEY_QUOTE, FieldType
from core.sql.model import Field, Table


class PypikaField(_PypikaField):
    @classmethod
    def get_field(cls, table: Table, field: Field, *args, **kwargs) -> "PypikaField":
        return cls(name=field.raw_name, table=table)


class MatchAllCriterion(Criterion):
    name = "MATCH_ALL"

    def __init__(self, term: Any, container: Union[list, tuple, set], alias: Optional[str] = None) -> None:
        super().__init__(alias)
        self.term = term
        self.container = self.wrap_constant(" ".join([str(item) for item in container]))
        self._is_negated = False

    def nodes_(self) -> Iterator[NodeT]:
        yield self
        yield from self.term.nodes_()

    @property
    def is_aggregate(self) -> Optional[bool]:
        return self.term.is_aggregate

    @builder
    def replace_table(self, current_table: Optional["Table"], new_table: Optional["Table"]) -> "MatchAllCriterion":
        self.term = self.term.replace_table(current_table, new_table)
        return self

    def get_sql(self, subquery: Any = None, **kwargs: Any) -> str:
        sql = "{term} {not_}{name} ({container})".format(
            term=self.term.get_sql(**kwargs),
            container=self.container.get_sql(with_alias=False, subquery=False, **kwargs),
            not_="NOT " if self._is_negated else "",
            name=self.name,
        )
        return format_alias_sql(sql, self.alias, **kwargs)

    @builder
    def negate(self) -> "MatchAllCriterion":
        self._is_negated = True
        return self


class MatchAnyCriterion(MatchAllCriterion):
    name = "MATCH_ANY"


class DorisField(PypikaField):
    """
    适用于 Doris 字段类型
    """

    key_quote: str = DORIS_FIELD_KEY_QUOTE

    @classmethod
    def get_field(cls, table: Table, field: Field, *args, **kwargs) -> "DorisField":
        return cls(name=field.raw_name, table=field.table)

    def match_all(self, arg: Union[list, tuple, set]) -> "MatchAllCriterion":
        return MatchAllCriterion(self, arg)

    def not_match_all(self, arg: Union[list, tuple, set]) -> "MatchAllCriterion":
        return MatchAllCriterion(self, arg).negate()

    def match_any(self, arg: Union[list, tuple, set]) -> "MatchAnyCriterion":
        return MatchAnyCriterion(self, arg)

    def not_match_any(self, arg: Union[list, tuple, set]) -> "MatchAnyCriterion":
        return MatchAnyCriterion(self, arg).negate()


class DorisPrimitiveField(DorisField):
    """
    Doris 普通类型字段支持
    """

    pass


class DorisVariantField(DorisField):
    """
    Doris variant类型字段支持
    """

    def __init__(self, keys: List[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.keys = keys

    @classmethod
    def get_field(cls, table: Table, field: Field, *args, **kwargs) -> "DorisField":
        return cls(keys=field.keys, *args, **kwargs)

    def _sanitize_variant_key(self, key: str) -> str:
        """对 Variant Key 做统一校验与转义，避免 SQL 注入"""
        # 1. 基础校验（非空类型）
        if not isinstance(key, str):
            raise TypeError(f"Variant Key 必须是字符串，当前类型：{type(key)}")
        if not key:
            raise ValueError("Variant Key 不能为空字符串")
            # 2. 使用 PyMySQL 提供的 escape_string 做转义
        escaped_key = escape_string(key)
        if isinstance(escaped_key, (bytes, bytearray)):
            escaped_key = escaped_key.decode()

        return escaped_key

    def format_keys_quote(self) -> str:
        """
        格式化keys，例如：["k1", "k2"] => "['k1']['k2']"
        """
        if not self.keys:
            return ""

        quote = self.key_quote or "'"
        return "".join(
            "[{quote}{key}{quote}]".format(
                key=self._sanitize_variant_key(key),
                quote=quote,
            )
            for key in self.keys
        )

    def get_sql(self, **kwargs: Any) -> str:
        if not self.keys:
            return super().get_sql(**kwargs)

        with_alias = kwargs.pop("with_alias", False)
        with_namespace = kwargs.pop("with_namespace", False)
        quote_char = kwargs.pop("quote_char", None)

        field_sql = format_quotes(self.name, quote_char) + self.format_keys_quote()

        # Need to add namespace if the table has an alias
        if self.table and (with_namespace or self.table.alias):
            table_name = self.table.get_table_name()
            field_sql = "{namespace}.{name}".format(
                namespace=format_quotes(table_name, quote_char),
                name=field_sql,
            )

        field_alias = getattr(self, "alias", None)
        if with_alias:
            return format_alias_sql(field_sql, field_alias, quote_char=quote_char, **kwargs)
        return field_sql


class DorisJsonTypeExtractFunction(Function):
    """
    Doris json类型字段检索支持
    """

    json_extract_functions = {
        FieldType.STRING: 'JSON_EXTRACT_STRING',
        FieldType.INT: 'JSON_EXTRACT_INT',
        FieldType.FLOAT: 'JSON_EXTRACT_DOUBLE',
        FieldType.DOUBLE: 'JSON_EXTRACT_DOUBLE',
        FieldType.LONG: 'JSON_EXTRACT_LARGEINT',
        FieldType.TEXT: 'JSON_EXTRACT_STRING',
        FieldType.TIMESTAMP: 'JSON_EXTRACT_LARGEINT',
    }

    def __init__(self, field: DorisField, keys: List[str], target_field_type: Optional[FieldType] = None, **kwargs):
        super().__init__(name='JSON_EXTRACT', **kwargs)
        self.target_field_type = target_field_type or FieldType.STRING
        self.name = self.json_extract_functions.get(
            self.target_field_type, self.json_extract_functions[FieldType.STRING]
        )
        self.args = [self.wrap_constant(param) for param in (field, f"$.{'.'.join(keys)}")]
