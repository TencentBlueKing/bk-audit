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

from typing import List

from django.utils.translation import gettext_lazy

from core.choices import TextChoices


class SOPSTaskStatus(TextChoices):
    """
    标准运维任务状态
    """

    # 其他状态
    CREATED = "CREATED", gettext_lazy("未执行")
    RUNNING = "RUNNING", gettext_lazy("执行中")
    SUSPENDED = "SUSPENDED", gettext_lazy("暂停")
    NODE_SUSPENDED = "NODE_SUSPENDED", gettext_lazy("节点暂停")
    EXPIRED = "EXPIRED", gettext_lazy("已过期")

    # 成功状态
    FINISHED = "FINISHED", gettext_lazy("执行成功")

    # 失败状态
    FAILED = "FAILED", gettext_lazy("执行失败")
    REVOKED = "REVOKED", gettext_lazy("已终止")

    @classmethod
    def get_success_status(cls) -> List["SOPSTaskStatus"]:
        return [cls.FINISHED]

    @classmethod
    def get_finished_status(cls) -> List["SOPSTaskStatus"]:
        return [cls.FINISHED, cls.FAILED, cls.REVOKED, cls.EXPIRED]

    @classmethod
    def get_failed_status(cls) -> List["SOPSTaskStatus"]:
        return [cls.FAILED, cls.REVOKED, cls.EXPIRED]


class SOPSTaskOperation(TextChoices):
    """
    操作任务
    """

    REVOKE = "revoke", gettext_lazy("终止任务")
    RETRY = "retry", gettext_lazy("重试")
