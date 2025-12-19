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

from bk_resource import api
from django.conf import settings

from core.models import get_request_username
from services.web.databus.models import RedisConfig


class RedisHandler:
    def __init__(self, redis_id: int = None):
        self.redis_config = None
        if redis_id:
            self.redis_config = RedisConfig.objects.get(redis_id=redis_id)

    def update_or_create(self, data: dict) -> None:
        """创建或更新"""

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

        # 更新
        if self.redis_config:
            api.bk_base.update_resource_set(**params)
            self.redis_config.redis_name = data["redis_name"]
            self.redis_config.admin = params["admin"]
            self.redis_config.connection_info = params["connection_info"]
            self.redis_config.version = params["version"]
            return self.redis_config

        # 创建
        api.bk_base.create_resource_set(**params)
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
