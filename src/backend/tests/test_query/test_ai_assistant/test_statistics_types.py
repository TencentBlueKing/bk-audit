"""类型化文本通道不能先经 float 丢失整数，也不能把空串当缺失。"""
from django.test import SimpleTestCase

from services.web.query.ai_assistant.log_tools import statistics_types


class TestStatisticsScalars(SimpleTestCase):
    def parse(self, kind, text):
        self.assertTrue(hasattr(statistics_types, "parse_statistics_scalar"), "missing strict typed scalar parser")
        return statistics_types.parse_statistics_scalar(kind, text)

    def test_typed_values_and_small_numbers_preserve_identity(self):
        for kind, text, value in [
            ("number", "1", 1),
            ("number", "1.0", 1),
            ("number", "-0", 0),
            ("string", '\"1\"', "1"),
            ("boolean", "true", True),
            ("string", '\"\"', ""),
            ("string", '\"null\"', "null"),
            ("number", "1e-20", 1e-20),
            ("number", "5e-324", 5e-324),
            ("number", "0.10000000000000001", 0.1),
            ("number", "9007199254740991", 9007199254740991),
        ]:
            with self.subTest(text=text, kind=kind):
                actual = self.parse(kind, text)
                self.assertEqual(actual, value)
                self.assertIs(type(actual), type(value))

    def test_unsafe_or_malformed_scalar_is_rejected(self):
        for kind, text in [
            ("number", "9007199254740992"),
            ("number", "9007199254740993"),
            ("number", "-9007199254740992"),
            ("number", "9.007199254740992e15"),
            ("number", "1e-400"),
            ("number", "NaN"),
            ("number", "Infinity"),
            ("number", "true"),
            ("string", "1"),
            ("boolean", '\"true\"'),
            ("number", "null"),
            ("number", "[]"),
            ("string", "{}"),
            ("number", 1.0),
        ]:
            with self.subTest(kind=kind, text=text):
                with self.assertRaises((ValueError, TypeError)):
                    self.parse(kind, text)
