from django.test import TestCase

from core.sql.exceptions import FilterValueError


class FilterValueErrorTests(TestCase):
    """
    测试 FilterValueError 错误消息格式化功能
    消息模板："条件表达式中字段 {field} 的值 {aggregation} {value} 无法转换成预期类型 {type}。"
    """

    def test_with_aggregation(self):
        """测试有聚合函数时的错误消息格式"""
        with self.assertRaises(FilterValueError) as context:
            raise FilterValueError(
                field="created_by",
                value="libywang",
                type="int",
                aggregation="count"
            )

        self.assertEqual(
            str(context.exception),
            "条件表达式中字段 created_by 的值 count (libywang) 无法转换成预期类型 int。"
        )

    def test_without_aggregation(self):
        """测试无聚合函数时的错误消息格式"""
        with self.assertRaises(FilterValueError) as context:
            raise FilterValueError(
                field="age",
                value="abc",
                type="int",
                aggregation=None
            )

        self.assertEqual(
            str(context.exception),
            "条件表达式中字段 age 的值  abc 无法转换成预期类型 int。"
        )

    def test_with_empty_aggregation(self):
        """测试聚合函数为空字符串时的消息格式"""
        with self.assertRaises(FilterValueError) as context:
            raise FilterValueError(
                field="price",
                value="high",
                type="float",
                aggregation=""
            )

        self.assertEqual(
            str(context.exception),
            "条件表达式中字段 price 的值  high 无法转换成预期类型 float。"
        )

    def test_numeric_value_with_aggregation(self):
        """测试数值类型值且有聚合函数的情况"""
        with self.assertRaises(FilterValueError) as context:
            raise FilterValueError(
                field="score",
                value=100,
                type="string",
                aggregation="avg"
            )

        self.assertEqual(
            str(context.exception),
            "条件表达式中字段 score 的值 avg (100) 无法转换成预期类型 string。"
        )

    def test_numeric_value_without_aggregation(self):
        """测试数值类型值且无聚合函数的情况"""
        with self.assertRaises(FilterValueError) as context:
            raise FilterValueError(
                field="quantity",
                value=50,
                type="datetime",
                aggregation=None
            )

        self.assertEqual(
            str(context.exception),
            "条件表达式中字段 quantity 的值  50 无法转换成预期类型 datetime。"
        )

    def test_special_characters_in_value(self):
        """测试值中包含特殊字符的情况"""
        with self.assertRaises(FilterValueError) as context:
            raise FilterValueError(
                field="name",
                value="john@example.com",
                type="int",
                aggregation="max"
            )

        self.assertEqual(
            str(context.exception),
            "条件表达式中字段 name 的值 max (john@example.com) 无法转换成预期类型 int。"
        )