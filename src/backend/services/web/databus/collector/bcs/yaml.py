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

import base64
import os.path

from django.conf import settings


class YamlTemplate:
    @classmethod
    def get(cls, value):
        template_path = os.path.join(
            settings.BASE_DIR, "services", "web", "databus", "collector", "bcs", "template.yml"
        )
        with open(template_path, encoding="utf-8") as file:
            template = file.read()
        template = template.format(log_config_type=value)
        return base64.b64encode(template.encode("utf-8")).decode("utf-8")
