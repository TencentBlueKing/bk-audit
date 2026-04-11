# -*- coding: utf-8 -*-

from iam import DjangoQuerySetConverter


class SceneDjangoQuerySetConverter(DjangoQuerySetConverter):
    """场景 IAM 策略 → Django Q 转换器"""

    def __init__(self):
        key_mapping = {"scene.id": "scene_id"}
        super().__init__(key_mapping)
