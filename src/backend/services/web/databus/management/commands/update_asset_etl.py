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

from django.core.management.base import BaseCommand, CommandError

from apps.meta.models import ResourceType, System
from services.web.databus.collector.snapshot.join.etl_storage import (
    AssetEtlStorageHandler,
)
from services.web.databus.models import Snapshot


class Command(BaseCommand):
    help = "更新指定资产的清洗配置（清洗+入库）"

    def add_arguments(self, parser):
        parser.add_argument("--system-id", required=True, help="系统ID")
        parser.add_argument("--resource-type-id", required=True, help="资源类型ID")
        parser.add_argument("--custom-config", help="写入 Snapshot.custom_config 的 JSON 对象")

    def parse_custom_config(self, raw_config: str | None) -> dict | None:
        if raw_config is None:
            return None
        try:
            custom_config = json.loads(raw_config)
        except json.JSONDecodeError as err:
            raise CommandError(f"--custom-config must be valid JSON: {err}") from err
        if not isinstance(custom_config, dict):
            raise CommandError("--custom-config must be a JSON object")
        return custom_config

    def handle(self, *args, **kwargs):
        system_id = kwargs["system_id"]
        resource_type_id = kwargs["resource_type_id"]
        custom_config = self.parse_custom_config(kwargs.get("custom_config"))

        snapshot = Snapshot.objects.get(system_id=system_id, resource_type_id=resource_type_id)
        system = System.objects.get(system_id=system_id)
        resource_type = ResourceType.objects.get(system_id=system_id, resource_type_id=resource_type_id)

        if custom_config is not None:
            snapshot.custom_config = custom_config
            snapshot.save(update_fields=["custom_config"])
            self.stdout.write("[update_asset_etl] 自定义配置已更新")

        self.stdout.write(
            f"[update_asset_etl] SystemID => {system_id}, ResourceTypeID => {resource_type_id}, "
            f"SnapshotID => {snapshot.id}"
        )

        for storage in snapshot.storages.all():
            self.stdout.write(f"[update_asset_etl] 处理 StorageType => {storage.storage_type}")

            handler = AssetEtlStorageHandler(
                data_id=snapshot.bkbase_data_id,
                system=system,
                resource_type=resource_type,
                storage_type=storage.storage_type,
                snapshot=snapshot,
            )

            # 更新清洗
            handler.create_clean(update=True)
            self.stdout.write(f"[update_asset_etl] 清洗配置已更新: processing_id => {snapshot.bkbase_processing_id}")

            # 更新入库
            handler.create_storage(update=True)
            self.stdout.write(f"[update_asset_etl] 入库配置已更新: StorageType => {storage.storage_type}")

        self.stdout.write(self.style.SUCCESS("[update_asset_etl] 全部更新完成"))
