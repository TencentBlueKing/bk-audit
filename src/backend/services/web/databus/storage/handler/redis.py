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

from apps.meta.models import System
from core.models import get_request_username
from services.web.bkbase import storage as bkbase_storage
from services.web.bkbase.common import get_bkbase_context, get_bkbase_version
from services.web.bkbase.constants import (
    BKBASE_V4_REDIS_BINDING,
    BKBaseVersion,
    RedisRegistrationState,
)
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.models import RedisConfig


class RedisHandler:
    def __init__(self, redis_id: int = None):
        self.redis_config = None
        if redis_id:
            self.redis_config = RedisConfig.objects.get(redis_id=redis_id)

    def update_or_create(self, data: dict) -> RedisConfig:
        """返回创建或更新后的记录；V4一期跳过已有实例更新并返回原记录。"""

        username = get_request_username()
        params = {
            "bk_username": username,
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "resource_set_id": data["redis_name_en"],
            "resource_set_name": data["redis_name"],
            "geog_area_code": settings.BKBASE_GEOG_AREA_CODE,
            "category": "redis",
            "provider": "user",
            "purpose": "Redis",
            "share": False,
            "admin": [username],
            "tag": settings.DEFAULT_REDIS_TAGS,
            "connection_info": data["connection_info"],
            "version": data["version"],
        }

        if get_bkbase_version() == BKBaseVersion.V4:
            if self.redis_config:
                # 一期跳过更新，返回原记录，不能将新连接信息伪记为已注册。
                bkbase_storage.update_resource_set(**params)
                return self.redis_config
            return bkbase_storage.register_redis_config(data, params)

        # 更新
        if self.redis_config:
            bkbase_storage.update_resource_set(**params)
            self.redis_config.redis_name = data["redis_name"]
            self.redis_config.admin = params["admin"]
            self.redis_config.connection_info = params["connection_info"]
            self.redis_config.version = params["version"]
            return self.redis_config

        # 创建
        bkbase_storage.create_resource_set(**params)
        redis_config = RedisConfig.objects.create(
            namespace=data["namespace"],
            redis_name_en=params["resource_set_id"],
            redis_name=params["resource_set_name"],
            admin=params["admin"],
            connection_info=params["connection_info"],
            version=params["version"],
        )
        return redis_config

    @classmethod
    def pick_redis(cls, system_id: str) -> RedisConfig:
        """随机获取Redis实例"""

        redis_configs = RedisConfig.objects.all()
        if get_bkbase_version() == BKBaseVersion.V4:
            namespace = System.objects.get(system_id=system_id).namespace
            context = get_bkbase_context()
            available = []
            for config in redis_configs.filter(namespace=namespace, is_deleted=False):
                binding = (config.extra or {}).get(BKBASE_V4_REDIS_BINDING)
                if binding is not None and binding.get("registration_state") != RedisRegistrationState.BOUND:
                    continue
                try:
                    bkbase_storage.resolve_storage_cluster(
                        context, audit_namespace=namespace, storage_type="redis", legacy_cluster_id=config.redis_name_en
                    )
                except BKBaseResourceMappingError:
                    continue
                available.append(config)
            if not available:
                raise BKBaseResourceMappingError(message="No Redis with a verified V4 binding is available")
            for config in available:
                if system_id in config.extra.get("systems", []):
                    return config
            redis_config = min(available, key=lambda config: config.extra.get("count", 0))
            redis_config.extra["count"] = redis_config.extra.get("count", 0) + 1
            redis_config.extra.setdefault("systems", []).append(system_id)
            redis_config.save(update_fields=["extra"])
            return redis_config

        for config in redis_configs:
            if system_id in config.extra.get("systems", []):
                return config

        redis_config = redis_configs.order_by("extra__count").first()
        count = redis_config.extra.get("count", 0) + 1
        redis_config.extra["count"] = count
        systems = redis_config.extra.get("systems", [])
        systems.append(system_id)
        redis_config.extra["systems"] = systems
        redis_config.save()
        return redis_config
