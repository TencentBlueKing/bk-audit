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

from typing import Union

from bk_resource.utils.text import underscore_to_camel
from django.conf import settings
from django.utils.module_loading import import_string

from apps.exceptions import FeatureNotExist
from apps.feature.constants import FeatureStatusChoices, FeatureTypeChoices
from apps.feature.models import FeatureToggle
from apps.feature.plugins import BaseFeaturePlugin


class FeatureHandler:
    """特性处理"""

    def __init__(self, feature_id: Union[str, FeatureTypeChoices]) -> None:
        self.feature_id = str(feature_id)
        self.feature = self.get_feature()

    def check(self) -> bool:
        """校验特性状态"""

        # 若为Off状态返回False
        if self.feature.status == FeatureStatusChoices.DENY.value:
            return False
        # 非测试环境返回False
        if self.feature.status == FeatureStatusChoices.STAG.value and settings.ENVIRONMENT not in ["dev", "stag"]:
            return False
        # 正式环境匹配
        if self.feature.status == FeatureStatusChoices.PROD.value and settings.ENVIRONMENT != "prod":
            return False
        # 其他情况返回True
        return True

    def get_feature(self) -> FeatureToggle:
        """获取Feature实例"""

        # 存在数据库Feature时优先返回
        db_feature = self._get_db_feature()
        if db_feature:
            feature = db_feature
        # 数据库未配置以设置为准
        else:
            setting_feature = self._get_setting_feature()
            feature = setting_feature
        return self._plugin_feature(feature)

    def _feature_exist(self) -> None:
        """校验Feature存在"""

        if self.feature_id not in settings.FEATURE_TOGGLE.keys():
            raise FeatureNotExist(message=FeatureNotExist.MESSAGE % self.feature_id)

    def _get_setting_feature(self) -> FeatureToggle:
        """从设置获取Feature"""

        # 校验Feature存在
        self._feature_exist()
        feature_status = settings.FEATURE_TOGGLE[self.feature_id]
        return FeatureToggle(
            feature_id=self.feature_id,
            status=feature_status,
        )

    def _get_db_feature(self) -> Union[FeatureToggle, None]:
        """从数据库获取Feature"""

        try:
            return FeatureToggle.objects.get(feature_id=self.feature_id)
        except FeatureToggle.DoesNotExist:
            return None

    def _plugin_feature(self, feature: FeatureToggle) -> FeatureToggle:
        plugin_path = f"feature.plugins.{underscore_to_camel(feature.feature_id)}Plugin"
        try:
            plugin = import_string(plugin_path)
        except ImportError:
            plugin = BaseFeaturePlugin
        return plugin(feature).feature
