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

from bk_audit.constants.log import DEFAULT_EMPTY_VALUE
from bk_audit.log.models import AuditInstance
from django.db import models
from django.utils.translation import gettext_lazy

from core.models import OperateRecordModel, SoftDeleteModel
from services.web.analyze.models import Control, ControlVersion
from services.web.strategy_v2.constants import StrategyStatusChoices


class Strategy(SoftDeleteModel):
    """
    Strategy
    """

    namespace = models.CharField(gettext_lazy("Namespace"), max_length=64)
    strategy_id = models.BigAutoField(gettext_lazy("Strategy ID"), primary_key=True)
    strategy_name = models.CharField(gettext_lazy("Strategy Name"), max_length=64)
    control_id = models.CharField(gettext_lazy("Control ID"), max_length=64)
    control_version = models.IntegerField(gettext_lazy("Version"))
    configs = models.JSONField(gettext_lazy("Configs"), default=dict, null=True, blank=True)
    status = models.CharField(
        gettext_lazy("Status"),
        max_length=64,
        choices=StrategyStatusChoices.choices,
        default=StrategyStatusChoices.STARTING.value,
    )
    status_msg = models.TextField(gettext_lazy("Status Message"), null=True, blank=True)
    backend_data = models.JSONField(gettext_lazy("Backend Data"), default=dict, null=True, blank=True)
    notice_groups = models.JSONField(gettext_lazy("Notice Groups"), default=list, null=True, blank=True)

    class Meta:
        verbose_name = gettext_lazy("Strategy")
        verbose_name_plural = verbose_name
        ordering = ["control_id", "-strategy_id"]

    @property
    def control_type_id(self):
        return Control.objects.get(control_id=self.control_id).control_type_id

    @property
    def control_version_inst(self) -> ControlVersion:
        return ControlVersion.objects.get(control_id=self.control_id, control_version=self.control_version)


class StrategyAuditInstance(AuditInstance):
    """
    Strategy Audit Instance
    """

    @property
    def instance_id(self):
        """
        实例ID
        @rtype: str
        """
        return getattr(self.instance, "strategy_id", DEFAULT_EMPTY_VALUE)

    @property
    def instance_name(self):
        """
        实例名
        @rtype: str
        """
        return getattr(self.instance, "strategy_name", DEFAULT_EMPTY_VALUE)

    @property
    def instance_data(self):
        """
        实例信息 JSON
        @rtype: dict
        """
        from services.web.strategy_v2.serializers import StrategyInfoSerializer

        return StrategyInfoSerializer(self.instance).data


class StrategyTag(OperateRecordModel):
    """
    Tag of Strategy, only used for left side panel
    """

    strategy_id = models.BigIntegerField(gettext_lazy("Strategy ID"))
    tag_id = models.BigIntegerField(gettext_lazy("Tag ID"))

    class Meta:
        verbose_name = gettext_lazy("Strategy Tag")
        verbose_name_plural = verbose_name
        ordering = ["-id"]
