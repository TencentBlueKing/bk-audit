"""校验 AI 助手公开错误码的唯一性。

请求响应和附件失败快照使用同一组错误码，不能让不同业务异常共用标识。
"""

import inspect
from collections import defaultdict

from django.test import SimpleTestCase

from services.web.ai_assistant import exceptions


class AIAssistantExceptionCodeTest(SimpleTestCase):
    """约束业务异常公开标识，避免新增异常与已有错误码冲突。"""

    def test_public_error_codes_are_unique(self):
        """不同业务异常必须产生不同的公开错误码。"""
        codes = defaultdict(list)
        for name, exception_type in inspect.getmembers(exceptions, inspect.isclass):
            if exception_type is exceptions.AIAssistantException or not issubclass(
                exception_type, exceptions.AIAssistantException
            ):
                continue
            codes[exception_type().code].append(name)

        duplicates = {code: names for code, names in codes.items() if len(names) > 1}
        self.assertEqual(duplicates, {})
