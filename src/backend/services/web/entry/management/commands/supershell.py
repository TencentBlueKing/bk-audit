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

import logging

from django.conf import settings
from django.core.management.commands.shell import Command as _Command


class Command(_Command):
    def handle(self, **options):
        for logger_name in settings.LOGGING["loggers"].keys():
            logger = logging.getLogger(logger_name)
            if any([type(handler) is logging.StreamHandler for handler in logger.handlers]):
                continue
            logger.addHandler(logging.StreamHandler())
        super().handle(**options)
