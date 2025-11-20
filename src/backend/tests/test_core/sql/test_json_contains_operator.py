import unittest

from pypika import Field as PypikaField

from core.sql.builder.utils import operate
from core.sql.constants import Operator


class TestJsonContainsOperator(unittest.TestCase):
    """
    验证 JSON_CONTAINS 操作符的 SQL 输出保持完整一致。
    """

    def test_json_contains_operator_generates_exact_sql(self):
        """
        operate 应返回完整的 JSON_CONTAINS(...) 片段，而不仅仅包含关键字。
        """

        field = PypikaField("strategy_tag_ids")
        criterion = operate(Operator.JSON_CONTAINS, field, '["1"]', [])
        expected_sql = 'JSON_CONTAINS("strategy_tag_ids",\'["1"]\')'
        self.assertEqual(str(criterion), expected_sql)
