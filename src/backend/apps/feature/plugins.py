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

import abc

from bk_resource import api
from django.conf import settings
from django.utils.translation import gettext

from apps.feature.constants import FeatureStatusChoices
from apps.feature.models import FeatureToggle


class BaseFeaturePlugin(abc.ABC):
    """特性插件"""

    def __init__(self, feature: FeatureToggle):
        self._feature = feature
        self._feature.status = self._update_status()

    @property
    def feature(self):
        return self._feature

    def _update_status(self):
        """通过此方法修改feature中的参数"""
        return self._feature.status


class BkbaseAiopsPlugin(BaseFeaturePlugin):
    """AIOPS插件"""

    def _update_status(self):
        # 若为关闭状态，不做校验
        if self.feature.status == FeatureStatusChoices.DENY.value:
            return FeatureStatusChoices.DENY.value
        # 其他状态需要获取AIOPS接口判断是否启用
        return FeatureStatusChoices.AVAILABLE.value if api.bk_base.check_aiops() else FeatureStatusChoices.DENY.value


class BklogOtlpPlugin(BaseFeaturePlugin):
    """OTLP插件"""

    def _update_status(self):
        # 更新参数
        config = self._feature.config or {}
        # 更新主机信息
        if not config.get("hosts"):
            hosts = []
            for bk_cloud_id, _hosts in api.bk_log.get_report_host().items():
                for _host in _hosts:
                    hosts.append("{}{} {}".format(gettext("云区域"), bk_cloud_id, _host))
            config["hosts"] = hosts
        # 更新 feature
        self._feature.config = config
        # 响应状态
        return self._feature.status


class BksecPlugin(BaseFeaturePlugin):
    """
    BKSEC 安全工单特性插件

    特性开启需同时满足：
      1. 必配环境变量齐全：
         BKSEC_PROJECT_ID（风险类型下拉维度）、
         BKSEC_SOPS_TEMPLATE_ID（预置发单套餐模板）、
         BKSEC_PLUGIN_CONFIG_API_URL（发单插件 Config 同步地址）；
      2. 已存在内置处理套餐（ProcessApplication.is_builtin=True, sops_template_id=BKSEC_SOPS_TEMPLATE_ID），
         即发单能力就绪。

    """

    # 必配环境变量
    REQUIRED_ENV = ("BKSEC_PROJECT_ID", "BKSEC_SOPS_TEMPLATE_ID", "BKSEC_PLUGIN_CONFIG_API_URL")

    def _update_status(self):
        # 显式关闭时不做校验，保留关闭状态
        if self.feature.status == FeatureStatusChoices.DENY.value:
            return FeatureStatusChoices.DENY.value

        from services.web.risk.models import ProcessApplication

        # 检查必配环境变量与内置套餐
        missing_env = [name for name in self.REQUIRED_ENV if not getattr(settings, name, None)]
        has_preset_pa = False
        template_id = getattr(settings, "BKSEC_SOPS_TEMPLATE_ID", None)
        if template_id:
            try:
                has_preset_pa = ProcessApplication.objects.filter(
                    is_builtin=True, sops_template_id=int(template_id)
                ).exists()
            except (TypeError, ValueError):
                pass
        self._feature.config = {
            "missing_env": missing_env,
            "has_preset_pa": has_preset_pa,
        }
        if missing_env or not has_preset_pa:
            return FeatureStatusChoices.DENY.value
        return FeatureStatusChoices.AVAILABLE.value
