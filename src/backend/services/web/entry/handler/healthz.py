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

import asyncio
import json

from bk_resource import api, resource
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger
from django.conf import settings
from redis import StrictRedis

from apps.exceptions import HealthzCheckFailed
from services.web.databus.models import RedisConfig


class MockData:
    """
    Mock 数据
    """

    class BkBaseCleanPreview:
        """
        数据平台清洗预览
        """

        msg = "start_abcdefg_end"
        conf = json.dumps(
            {
                "type": "fun",
                "method": "regex_extract",
                "label": "label00001",
                "args": [{"result": "data", "keys": ["content"], "regexp": r"start_(?<content>\w+)_end"}],
                "next": None,
            }
        )


class HealthzHandler(object):
    """
    HealthzHandler
    """

    def __init__(self):
        # 检查ES
        self.es_errors = []
        self.check_es()
        # 检查Redis
        self.redis_errors = []
        self.check_redis()
        # 检查API
        self.api_errors = []
        # self.check_api()
        # 默认为正常
        self.healthy = True
        self.errors = {}
        for key in ["es_errors", "redis_errors", "api_errors"]:
            if not getattr(self, key, []):
                continue
            self.healthy = False
            self.errors[key] = getattr(self, key)

    @property
    def healthz(self) -> dict:
        """
        入口函数
        """

        if self.healthy:
            return {"healthy": True}
        exception = HealthzCheckFailed()
        logger.exception("[HealthzCheckFailed] Err => %s", self.errors)
        raise exception

    def check_es(self) -> None:
        """
        检查ES状态
        """

        clusters = resource.storage.storage_list(namespace=settings.DEFAULT_NAMESPACE)
        cluster_data = api.bk_log.batch_connectivity_detect(
            cluster_ids=",".join([str(c["cluster_config"]["cluster_id"]) for c in clusters]), _is_backend=True
        )
        for cluster_id, result in cluster_data.items():
            if result:
                continue
            self.es_errors.append(cluster_id)

    def check_redis(self) -> None:
        """
        检查Redis状态
        """

        redis_configs = RedisConfig.objects.filter(is_deleted=False)
        for redis_config in redis_configs:
            try:
                connection_info = redis_config.connection_info
                if connection_info.get("enable_sentinel", False):
                    continue
                else:
                    client = StrictRedis(
                        host=connection_info["host"], port=connection_info["port"], password=connection_info["password"]
                    )
                    client.ping()
            except Exception as err:  # NOCC:broad-except(需要处理所有错误)
                logger.exception("[CheckRedisFailed] RedisID => %s; Err => %s", redis_config.redis_id, err)
                self.redis_errors.append({redis_config.redis_id: str(err)})

    def check_api(self) -> None:
        """
        检查API状态
        """

        # 获取Loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Tasks
        tasks = [
            # 检查bk_base
            self._check_api(
                api.bk_base.clean_preview,
                msg=MockData.BkBaseCleanPreview.msg,
                conf=MockData.BkBaseCleanPreview.conf,
                debug_by_step=True,
            ),
            # 检查bk_cmsi
            self._check_api(api.bk_cmsi.get_msg_type),
            # 检查bk_iam
            self._check_api(api.bk_iam.get_systems),
            # 检查bk_log
            self._check_api(api.bk_log.get_spaces_mine),
            # 检查bk_monitor
            self._check_api(api.bk_monitor.search_notice_group),
            # 检查bk_paas
            self._check_api(
                api.bk_paas.uni_apps_query, id=settings.APP_CODE, include_deploy_info=True, include_market_info="true"
            ),
        ]
        # 等待任务结束
        loop.run_until_complete(asyncio.wait(tasks))
        loop.close()

    async def _check_api(self, func: callable, *args, **kwargs) -> None:
        """
        实际检查API，并更新错误信息
        """

        try:
            func(*args, **kwargs, _is_backend=True)
        except APIRequestError as err:
            self.api_errors.append({func.__class__.__name__: str(err)})
