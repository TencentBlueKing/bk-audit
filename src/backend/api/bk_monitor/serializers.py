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

import datetime

from django.utils.translation import gettext_lazy
from rest_framework import serializers


class MetricDataSerializer(serializers.Serializer):
    target = serializers.CharField(label=gettext_lazy("来源标识如IP"))
    metrics = serializers.DictField(label=gettext_lazy("自定义指标"))
    dimension = serializers.DictField(label=gettext_lazy("自定义维度"), default=dict)
    timestamp = serializers.IntegerField(label=gettext_lazy("数据时间(ms)"), default=0)

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        if not data["timestamp"]:
            data["timestamp"] = int(datetime.datetime.now().timestamp() * 1000)
        return data


class ReportMetricSerializer(serializers.Serializer):
    data_id = serializers.IntegerField(label=gettext_lazy("数据通道标识"), min_value=0)
    access_token = serializers.CharField(label=gettext_lazy("数据通道标识验证码"))
    data = MetricDataSerializer(label=gettext_lazy("指标数据"), many=True)


# 事件数据序列化器
class EventDataSerializer(MetricDataSerializer):
    event_name = serializers.CharField(label=gettext_lazy("事件名称"))
    event = serializers.DictField(label=gettext_lazy("事件内容"))
    metrics = None


class ReportEventSerializer(ReportMetricSerializer):
    data = EventDataSerializer(label=gettext_lazy("事件数据"), many=True)
