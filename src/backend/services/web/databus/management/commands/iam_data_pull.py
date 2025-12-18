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

from django.core.management.base import BaseCommand

from services.web.databus.collector.snapshot.system import create_iam_data_link


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("-t", choices=["resource_type", "action"], required=True)
        parser.add_argument("--url", required=False)

    def handle(self, *args, **kwargs):
        create_iam_data_link(kwargs["t"])
