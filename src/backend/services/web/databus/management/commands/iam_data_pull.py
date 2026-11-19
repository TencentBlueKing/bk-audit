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

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from services.web.bkbase.common import get_bkbase_version
from services.web.bkbase.constants import BKBaseVersion
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector.snapshot.system.base import create_iam_data_link


class Command(BaseCommand):
    def add_arguments(self, parser):
        kinds = ["resource_type", "action"]
        if get_bkbase_version() == BKBaseVersion.V4:
            kinds.append("user")
        parser.add_argument("-t", choices=kinds, required=True)
        parser.add_argument("--url", required=False)
        parser.add_argument("--v4-binding-file", help="Path to the explicit IAM V4 snapshot migration binding")

    def handle(self, *args, **kwargs):
        kind = kwargs["t"]
        filename = kwargs["v4_binding_file"]
        try:
            if filename:
                if get_bkbase_version() != BKBaseVersion.V4:
                    raise CommandError("--v4-binding-file requires BKBase V4")
                try:
                    binding = json.loads(Path(filename).read_text(encoding="utf-8"))
                except (OSError, ValueError) as error:
                    raise CommandError("Unable to read the IAM V4 snapshot binding JSON") from error
                if not isinstance(binding, dict):
                    raise CommandError("The IAM V4 snapshot binding must be a JSON object")
                waiting_for = create_iam_data_link(kind, migration_binding=binding)
            else:
                waiting_for = create_iam_data_link(kind)
        except BKBaseResourceMappingError as error:
            raise CommandError(str(error)) from error
        if waiting_for is not None:
            raise CommandError(f"IAM V4 {kind} snapshot pending: {waiting_for}")
