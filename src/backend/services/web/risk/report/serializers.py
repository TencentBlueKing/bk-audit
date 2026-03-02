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

from typing import List

from django.utils.translation import gettext_lazy
from rest_framework import serializers

from core.serializers import (
    ChoiceDisplayField,
    CommaSeparatedListField,
    FriendlyDateTimeField,
)
from services.web.risk.constants import RiskLabel, RiskStatus
from services.web.risk.models import Risk
from services.web.strategy_v2.constants import RiskLevel


class ReportRiskVariableSerializer(serializers.ModelSerializer):
    """
    报告风险变量序列化器

    用于定义报告模板中可引用的风险字段，替代 REPORT_RISK_VARIABLES 常量。
    每个字段通过 label 和 help_text 提供元信息，支持通过 get_field_definitions() 获取字段定义列表。

    特性：
    - 枚举字段自动翻译为中文 label（如 "HIGH" -> "高"）
    - 时间字段自动转换为本地时区标准格式（如 "2025-01-19 21:00:00"）
    """

    # Risk 模型自有字段
    risk_id = serializers.CharField(
        label=gettext_lazy("风险ID"),
        help_text=gettext_lazy("风险单唯一标识"),
    )
    title = serializers.CharField(
        label=gettext_lazy("风险标题"),
        help_text=gettext_lazy("风险单标题"),
    )
    status = ChoiceDisplayField(
        choices=RiskStatus,
        label=gettext_lazy("风险状态"),
        help_text=gettext_lazy("当前风险处理状态"),
    )
    event_time = FriendlyDateTimeField(
        label=gettext_lazy("首次发现时间"),
        help_text=gettext_lazy("风险首次发现时间"),
    )
    event_end_time = FriendlyDateTimeField(
        label=gettext_lazy("最后发现时间"),
        help_text=gettext_lazy("风险最后发现时间"),
    )
    operator = CommaSeparatedListField(
        label=gettext_lazy("责任人"),
        help_text=gettext_lazy("风险相关的责任人列表"),
    )
    risk_label = ChoiceDisplayField(
        choices=RiskLabel,
        label=gettext_lazy("风险标记"),
        help_text=gettext_lazy("风险标记（正常/误报）"),
    )
    strategy_id = serializers.IntegerField(
        label=gettext_lazy("命中策略ID"),
        help_text=gettext_lazy("触发风险的策略ID"),
        source="strategy.strategy_id",
        allow_null=True,
    )
    event_type = serializers.JSONField(
        label=gettext_lazy("风险类型"),
        help_text=gettext_lazy("事件类型标签列表"),
    )
    current_operator = CommaSeparatedListField(
        label=gettext_lazy("当前处理人"),
        help_text=gettext_lazy("当前负责处理的人员"),
    )
    notice_users = CommaSeparatedListField(
        label=gettext_lazy("关注人"),
        help_text=gettext_lazy("关注该风险的用户列表"),
    )
    last_operate_time = FriendlyDateTimeField(
        label=gettext_lazy("最后处理时间"),
        help_text=gettext_lazy("最后一次操作时间"),
    )
    created_at = FriendlyDateTimeField(
        label=gettext_lazy("创建时间"),
        help_text=gettext_lazy("风险单创建时间"),
    )
    updated_at = FriendlyDateTimeField(
        label=gettext_lazy("更新时间"),
        help_text=gettext_lazy("风险单更新时间"),
    )

    # 来自关联的 Strategy 模型的字段
    risk_level = ChoiceDisplayField(
        choices=RiskLevel,
        label=gettext_lazy("风险等级"),
        help_text=gettext_lazy("风险等级标签（高/中/低）"),
        source="strategy.risk_level",
    )
    risk_hazard = serializers.CharField(
        label=gettext_lazy("风险危害"),
        help_text=gettext_lazy("来自策略配置"),
        source="strategy.risk_hazard",
    )
    risk_guidance = serializers.CharField(
        label=gettext_lazy("处理指引"),
        help_text=gettext_lazy("来自策略配置"),
        source="strategy.risk_guidance",
    )

    class Meta:
        model = Risk
        fields = [
            "risk_id",
            "title",
            "status",
            "risk_level",
            "event_time",
            "event_end_time",
            "operator",
            "risk_label",
            "strategy_id",
            "risk_hazard",
            "risk_guidance",
            "event_type",
            "current_operator",
            "notice_users",
            "last_operate_time",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        """
        重写序列化方法，统一将空值转为空字符串
        """
        data = super().to_representation(instance)
        # 统一将空值转为空字符串
        return {key: ("" if value is None else value) for key, value in data.items()}

    @classmethod
    def get_field_definitions(cls) -> List[dict]:
        """
        获取字段定义列表

        返回序列化器中所有字段的元信息，用于替代原 REPORT_RISK_VARIABLES 常量。

        Returns:
            List[dict]: 字段定义列表，每个元素包含:
                - field: 字段名称
                - name: 字段显示名称（对应 label）
                - description: 字段描述（对应 help_text）
        """
        serializer = cls()
        definitions = []
        for field_name in cls.Meta.fields:
            field = serializer.fields[field_name]
            definitions.append(
                {
                    "field": field_name,
                    "name": str(field.label) if field.label else "",
                    "description": str(field.help_text) if field.help_text else "",
                }
            )
        return definitions
