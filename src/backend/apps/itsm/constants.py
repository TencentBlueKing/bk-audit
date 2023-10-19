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

ITSM_SERVICE_CATALOG_ID_KEY = "ITSM_SERVICE_CATALOG_ID"
ITSM_SERVICE_PROJECT_ID_KEY = "ITSM_SERVICE_PROJECT_ID"


class TicketStatus(TextChoices):
    WAIT = "WAIT", gettext_lazy("待处理")
    RUNNING = "RUNNING", gettext_lazy("审批中")
    RECEIVING = "RECEIVING", gettext_lazy("待认领")
    DISTRIBUTING = "DISTRIBUTING", gettext_lazy("待分派")
    TERMINATED = "TERMINATED", gettext_lazy("被终止")
    FINISHED = "FINISHED", gettext_lazy("已结束")
    FAILED = "FAILED", gettext_lazy("执行失败")
    REVOKED = "REVOKED", gettext_lazy("被撤销")
    SUSPEND = "SUSPEND", gettext_lazy("被挂起")

    @classmethod
    def get_success_status(cls) -> List["TicketStatus"]:
        return [cls.FINISHED]

    @classmethod
    def get_finished_status(cls) -> List["TicketStatus"]:
        return [cls.FINISHED, cls.TERMINATED, cls.FAILED, cls.REVOKED]

    @classmethod
    def get_failed_status(cls) -> List["TicketStatus"]:
        return [cls.TERMINATED, cls.FAILED, cls.REVOKED]


class TicketOperate(TextChoices):
    WITHDRAW = "WITHDRAW", gettext_lazy("撤销")
