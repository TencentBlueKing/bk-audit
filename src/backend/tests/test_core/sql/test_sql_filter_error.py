from unittest.mock import MagicMock

from django.test import TestCase

from core.sql.constants import AggregateType, FieldType, Operator
from core.sql.exceptions import FilterValueError
from core.sql.model import Condition, Field
from core.sql.sql_builder import QueryBuilder, SQLGenerator


class FilterValueErrorTests(TestCase):
    """
    测试 FilterValueError 错误消息格式化功能
    消息模板："条件表达式中字段 {field} 的值 {aggregation} {value} 无法转换成预期类型 {type}。"
    """

    def setUp(self):
        self.mock_query_builder = MagicMock(spec=QueryBuilder)
        self.generator = SQLGenerator(self.mock_query_builder)
        # 手动初始化 table_map
        self.generator.table_map = {"test_table": MagicMock()}

        # 初始化测试字段
        self.int_field = Field(
            table="test_table",
            raw_name="age",
            display_name="年龄",
            field_type=FieldType.INT,
        )
        self.count_field = Field(
            table="test_table",
            raw_name="user_count",
            display_name="用户数",
            field_type=FieldType.LONG,
            aggregate=AggregateType.COUNT,
        )

    def test_with_aggregation(self):
        """测试有聚合函数时的错误消息格式"""
        with self.assertRaises(FilterValueError) as context:
            raise FilterValueError(field="created_by", value="libywang", type="int", aggregation="count")

        self.assertEqual(str(context.exception), "条件表达式中字段 created_by 的值 count (libywang) 无法转换成预期类型 int。")

    def test_without_aggregation(self):
        """测试无聚合函数时的错误消息格式"""
        with self.assertRaises(FilterValueError) as context:
            raise FilterValueError(field="age", value="abc", type="int", aggregation=None)

        self.assertEqual(str(context.exception), "条件表达式中字段 age 的值  abc 无法转换成预期类型 int。")

    def test_with_empty_aggregation(self):
        """测试聚合函数为空字符串时的消息格式"""
        with self.assertRaises(FilterValueError) as context:
            raise FilterValueError(field="price", value="high", type="float", aggregation="")

        self.assertEqual(str(context.exception), "条件表达式中字段 price 的值  high 无法转换成预期类型 float。")

    def test_numeric_value_with_aggregation(self):
        """测试数值类型值且有聚合函数的情况"""
        with self.assertRaises(FilterValueError) as context:
            raise FilterValueError(field="score", value=100, type="string", aggregation="avg")

        self.assertEqual(str(context.exception), "条件表达式中字段 score 的值 avg (100) 无法转换成预期类型 string。")

    def test_numeric_value_without_aggregation(self):
        """测试数值类型值且无聚合函数的情况"""
        with self.assertRaises(FilterValueError) as context:
            raise FilterValueError(field="quantity", value=50, type="datetime", aggregation=None)

        self.assertEqual(str(context.exception), "条件表达式中字段 quantity 的值  50 无法转换成预期类型 datetime。")

    def test_special_characters_in_value(self):
        """测试值中包含特殊字符的情况"""
        with self.assertRaises(FilterValueError) as context:
            raise FilterValueError(field="name", value="john@example.com", type="int", aggregation="max")

        self.assertEqual(str(context.exception), "条件表达式中字段 name 的值 max (john@example.com) 无法转换成预期类型 int。")

    def test_normal_field_invalid_int_conversion(self):
        """测试普通整数字段值转换失败"""
        condition = Condition(
            field=self.int_field,
            operator=Operator.EQ,
            filter="abc",  # 无法转换为 int
        )

        with self.assertRaises(FilterValueError) as cm:
            self.generator.handle_condition(condition)

        self.assertEqual(str(cm.exception), "条件表达式中字段 age 的值  abc 无法转换成预期类型 <class 'int'>。")

    def test_aggregate_field_count_conversion_failure(self):
        """测试 COUNT 聚合字段值转换失败"""
        condition = Condition(
            field=self.count_field,
            operator=Operator.EQ,
            filter="xyz",  # 无法转换为 int（COUNT 结果为 LONG）
        )

        with self.assertRaises(FilterValueError) as cm:
            self.generator.handle_condition(condition)

        self.assertEqual(str(cm.exception), "条件表达式中字段 user_count 的值 COUNT (xyz) 无法转换成预期类型 <class 'int'>。")

    def test_aggregate_field_sum_conversion_failure(self):
        """测试 SUM 聚合字段值转换失败"""
        sum_field = Field(
            table="test_table",
            raw_name="total_amount",
            display_name="总金额",
            field_type=FieldType.DOUBLE,
            aggregate=AggregateType.SUM,
        )
        condition = Condition(
            field=sum_field,
            operator=Operator.LT,
            filter="invalid_number",  # 无效数值
        )

        with self.assertRaises(FilterValueError) as cm:
            self.generator.handle_condition(condition)

        self.assertEqual(str(cm.exception), "条件表达式中字段 total_amount 的值 SUM (invalid_number) 无法转换成预期类型 <class 'float'>。")

    def test_list_field_invalid_int_conversion(self):
        """测试 IN 操作符列表值转整数失败"""
        condition = Condition(
            field=self.int_field,
            operator=Operator.INCLUDE,
            filters=["1a", "b2"],  # 包含非整数
        )

        with self.assertRaises(FilterValueError) as cm:
            self.generator.handle_condition(condition)

        self.assertEqual(str(cm.exception), "条件表达式中字段 age 的值  ['1a', 'b2'] 无法转换成预期类型 <class 'int'>。")

    def test_list_field_invalid_timestamp_conversion(self):
        """测试 EXCLUDE 操作符列表值转时间戳失败"""
        timestamp_field = Field(
            table="test_table",
            raw_name="create_time",
            display_name="创建时间",
            field_type=FieldType.TIMESTAMP,  # 时间戳对应 int
            aggregate=None,
        )
        condition = Condition(
            field=timestamp_field,
            operator=Operator.EXCLUDE,
            filters=["2023-13-32", "invalid-date"],  # 无效日期字符串
        )

        with self.assertRaises(FilterValueError) as cm:
            self.generator.handle_condition(condition)

        self.assertEqual(
            str(cm.exception), "条件表达式中字段 create_time 的值  ['2023-13-32', 'invalid-date'] 无法转换成预期类型 <class 'int'>。"
        )
