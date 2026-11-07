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
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations
under the License.
We undertake not to change the open source license (MIT license) that applies
to the current version of the project delivered to anyone in the future.
"""

import uuid
from typing import Optional

from blueapps.utils.logger import logger
from django.core.cache import cache


class SyncExportSlotLease:
    """同步导出全局并发槽（Redis 租约式，参照 core.lock.CacheLock 的保守策略）。

    每个槽位是独立缓存键，``cache.add`` 原子占位（同键只允许一个持有人）：
    - 占满即拒：``acquire`` 返回 None，调用方直接降级异步，**不排队不等待**
      （等待本身就是超时源）；
    - 租约自带 TTL：进程崩溃后自动过期自愈，无需显式释放；
    - 正常路径由持有人释放，释放前比对持有 token，避免误删他人接位后的新租约
      （get/delete 非原子仅存极小竞态窗口，残余影响为上限瞬时 +1，可接受）；
    - Redis 异常按"满槽"处理（保守拒绝 → 调用方降级异步），宁可降级不可超时。
    """

    def __init__(self, *, key_prefix: str, max_concurrency: int, lease_seconds: int):
        self.key_prefix = key_prefix
        self.max_concurrency = max_concurrency
        self.lease_seconds = lease_seconds
        self.token = uuid.uuid4().hex
        self.slot_key: Optional[str] = None

    def acquire(self) -> Optional[str]:
        """尝试占一个槽位，成功返回槽位键，满槽/异常返回 None。"""

        if self.max_concurrency <= 0:
            return None
        for index in range(self.max_concurrency):
            slot_key = f"{self.key_prefix}:{index}"
            try:
                if cache.add(slot_key, self.token, timeout=self.lease_seconds):
                    self.slot_key = slot_key
                    logger.info("[SyncExportSlotLease] slot acquired, key=%s", slot_key)
                    return slot_key
            except Exception as error:  # pylint: disable=broad-except
                # Redis 故障按满槽处理：同步导出降级异步无损，反向（放行）才会超时
                logger.warning("[SyncExportSlotLease] redis error, key=%s, error=%s", slot_key, error)
                return None
        logger.warning("[SyncExportSlotLease] all %d slots busy", self.max_concurrency)
        return None

    def release(self) -> None:
        """释放自己持有的槽位；未持有或已释放时为空操作。"""

        if self.slot_key is None:
            return
        slot_key, self.slot_key = self.slot_key, None
        try:
            if cache.get(slot_key) == self.token:
                cache.delete(slot_key)
                logger.info("[SyncExportSlotLease] slot released, key=%s", slot_key)
        except Exception as error:  # pylint: disable=broad-except
            # 释放失败仅依赖 TTL 自愈，不影响主流程
            logger.warning("[SyncExportSlotLease] release error, key=%s, error=%s", slot_key, error)
