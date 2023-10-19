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
import os.path

from django.conf import settings
from django.db import transaction

from services.web.version.models import VersionLog


def get_version_id(version: str) -> str:
    return version.rsplit(".", 1)[0]


def get_version_language(version: str) -> str:
    return version.rsplit(".", 1)[1]


def parse_file_name(file_name: str) -> (str, datetime):
    version, release_at_str, language = str(file_name).replace(".md", "").split("_", 2)
    release_at = datetime.datetime.strptime(release_at_str, "%Y%m%d")
    return f"{version}.{language}", release_at


def init_version_log(sender, **kwargs):
    version_dir = os.path.join(settings.BASE_DIR, settings.VERSION_MD_DIR)
    version_files = os.listdir(version_dir)
    versions = []
    for file_name in version_files:
        with open(os.path.join(version_dir, file_name), "r", encoding="utf-8") as file:
            version, publish_at = parse_file_name(str(file_name))
            versions.append(
                VersionLog(
                    release_at=publish_at,
                    version=version,
                    content=file.read(),
                )
            )
    with transaction.atomic():
        VersionLog.objects.all().delete()
        VersionLog.objects.bulk_create(versions)
