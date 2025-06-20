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

from django.utils.translation import gettext_lazy
from rest_framework import serializers


class SqlAnalyseRequestSerializer(serializers.Serializer):
    """SQL 分析请求参数"""

    sql = serializers.CharField(label=gettext_lazy("SQL"))
    dialect = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)


class SqlVariableSerializer(serializers.Serializer):
    raw_name = serializers.CharField(label=gettext_lazy("变量名"))
    required = serializers.BooleanField(label=gettext_lazy("是否必填"), default=True)
    display_name = serializers.CharField(label=gettext_lazy("展示名称"), allow_blank=True, allow_null=True, default=None)


class SelectFieldSerializer(serializers.Serializer):
    display_name = serializers.CharField(label=gettext_lazy("展示名称"))
    raw_name = serializers.CharField(label=gettext_lazy("原始名称"), allow_blank=True, allow_null=True, required=False)


class TableSerializer(serializers.Serializer):
    table_name = serializers.CharField(label=gettext_lazy("表名"))
    alias = serializers.CharField(label=gettext_lazy("别名"), allow_blank=True, allow_null=True, required=False)


class SqlAnalyseResponseSerializer(serializers.Serializer):
    referenced_tables = TableSerializer(many=True)
    sql_variables = SqlVariableSerializer(many=True)
    result_fields = SelectFieldSerializer(many=True)
    original_sql = serializers.CharField()
    dialect = serializers.CharField(allow_null=True, required=False)
