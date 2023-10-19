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
