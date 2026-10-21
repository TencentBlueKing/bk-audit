# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import os

from bk_resource import BkApiResource

from api.domains import BKSEC_PLUGIN_CONFIG_API_URL


class BkSecSendPlugin(BkApiResource):
    """BKSEC 发单插件 API 基类"""

    module_name = "bk_sec_send_plugin"

    @property
    def base_url(self) -> str:
        return BKSEC_PLUGIN_CONFIG_API_URL

    def add_esb_info_before_request(self, params: dict) -> dict:
        """模拟上云环境应用身份：CODE 与 SECRET 需成对配置、"""
        plugin_app_code = os.getenv("BKAPP_BKSEC_PLUGIN_APP_CODE")
        plugin_app_secret = os.getenv("BKAPP_BKSEC_PLUGIN_APP_SECRET")
        if plugin_app_code and plugin_app_secret:
            params["bk_app_code"] = plugin_app_code
            params["bk_app_secret"] = plugin_app_secret
            return params
        return super().add_esb_info_before_request(params)


class ConfigUpsert(BkSecSendPlugin):
    """插件 Config 同步"""

    name = "同步插件 Config"
    method = "POST"
    action = ""
    IS_STANDARD_FORMAT = False
