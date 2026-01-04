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

from django.conf import settings
from django.utils.translation import gettext_lazy
from rest_framework import serializers


class LogSubscriptionQuerySerializer(serializers.Serializer):
    """日志订阅查询请求序列化器"""

    token = serializers.UUIDField(label=gettext_lazy("订阅 Token"), help_text=gettext_lazy("订阅配置的唯一标识"))

    source_id = serializers.CharField(label=gettext_lazy("数据源标识"), help_text=gettext_lazy("指定查询的数据源，如 audit_log"))

    start_time = serializers.IntegerField(label=gettext_lazy("开始时间(ms)"), help_text=gettext_lazy("Unix 毫秒时间戳"))

    end_time = serializers.IntegerField(label=gettext_lazy("结束时间(ms)"), help_text=gettext_lazy("Unix 毫秒时间戳"))

    page = serializers.IntegerField(label=gettext_lazy("页码"), min_value=1, default=1)

    page_size = serializers.IntegerField(label=gettext_lazy("单页数量"), min_value=1, max_value=1000, default=100)

    fields = serializers.ListField(
        child=serializers.CharField(),
        label=gettext_lazy("返回字段"),
        required=False,
        allow_empty=False,
        help_text=gettext_lazy("指定返回哪些字段，不传则返回全部字段（SELECT *）。字段是否存在由 SQL 查询时数据库校验"),
    )

    filters = serializers.JSONField(
        label=gettext_lazy("自定义筛选条件"),
        required=False,
        allow_null=True,
        help_text=gettext_lazy("WhereCondition JSON 格式的额外筛选条件，会与订阅配置的条件 AND 合并"),
    )

    raw = serializers.BooleanField(
        label=gettext_lazy("仅返回 SQL"),
        required=False,
        default=False,
        help_text=gettext_lazy("设置为 true 时仅返回 SQL 不执行查询"),
    )

    def validate_filters(self, value):
        """
        验证自定义筛选条件，检查是否包含 keys 字段（暂不支持），并为 field 对象补充默认值

        参考 _replace_table_name 的实现方式，递归检查 field.keys

        Args:
            value: WhereCondition 格式的字典

        Returns:
            验证后的值（已补充默认值）

        Raises:
            ValidationError: 如果包含 keys 字段
        """
        if not value:
            return value

        def process_condition(condition_dict):
            """
            递归处理条件：检查 keys 字段并为 field 补充默认值

            Args:
                condition_dict: WhereCondition 格式的字典

            Returns:
                bool: 如果找到 keys 字段返回 True
            """
            if not isinstance(condition_dict, dict):
                return False

            # 如果是叶子节点（包含 condition 字段）
            if "condition" in condition_dict and isinstance(condition_dict["condition"], dict):
                condition = condition_dict["condition"]
                if "field" in condition and isinstance(condition["field"], dict):
                    field = condition["field"]
                    # 检查是否包含 keys 字段
                    if "keys" in field:
                        return True
                    # 为 field 补充默认值：table 默认为 "t"，display_name 默认为 raw_name
                    if "table" not in field:
                        field["table"] = "t"
                    if "display_name" not in field and "raw_name" in field:
                        field["display_name"] = field["raw_name"]

            # 如果是组合节点（包含 conditions 列表），递归处理每个子条件
            if "conditions" in condition_dict and isinstance(condition_dict["conditions"], list):
                for sub_condition in condition_dict["conditions"]:
                    if process_condition(sub_condition):
                        return True

            return False

        if process_condition(value):
            raise serializers.ValidationError(gettext_lazy("自定义筛选条件不支持 keys 字段"))

        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if attrs["start_time"] > attrs["end_time"]:
            raise serializers.ValidationError({"time_range": gettext_lazy("开始时间需小于等于结束时间")})

        # 时间范围限制（防止查询过大范围）
        max_time_range = settings.LOG_SUBSCRIPTION_MAX_TIME_RANGE
        time_range = attrs["end_time"] - attrs["start_time"]
        if time_range > max_time_range:
            max_days = max_time_range / (24 * 60 * 60 * 1000)
            raise serializers.ValidationError(
                {"time_range": gettext_lazy("时间范围不能超过 {days} 天").format(days=int(max_days))}
            )

        return attrs


class LogSubscriptionQueryResponseSerializer(serializers.Serializer):
    """日志订阅查询响应序列化器"""

    page = serializers.IntegerField(label=gettext_lazy("页码"))

    page_size = serializers.IntegerField(label=gettext_lazy("单页数量"))

    total = serializers.IntegerField(label=gettext_lazy("总数"))

    results = serializers.ListField(
        label=gettext_lazy("数据"),
        child=serializers.JSONField(),
        allow_empty=True,
        help_text=gettext_lazy("透传 BKBase 查询结果，字段结构由数据源配置和请求参数决定"),
    )

    query_sql = serializers.CharField(label=gettext_lazy("查询 SQL"), help_text=gettext_lazy("实际执行的查询 SQL"))

    count_sql = serializers.CharField(label=gettext_lazy("统计 SQL"), help_text=gettext_lazy("实际执行的统计 SQL"))
