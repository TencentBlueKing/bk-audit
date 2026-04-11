# -*- coding: utf-8 -*-

from iam import DjangoQuerySetConverter


class SystemDjangoQuerySetConverter(DjangoQuerySetConverter):
    """系统 IAM 策略 → Django Q 转换器"""

    def __init__(self):
        key_mapping = {"system.id": "system_id"}
        super().__init__(key_mapping)
