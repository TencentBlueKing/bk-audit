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

from apps.notice.senders.base import Sender
from core.bk_api_base import AuditBkApiResource

# v1 多租户模式下，企业微信 agentid/corpsecret 为顶层参数，需从消息体中剥离
_WEIXIN_TOP_LEVEL_KEYS = ("wx_qy_agentid", "wx_qy_corpsecret")


class WeixinSender(Sender):
    """
    发送微信消息
    """

    api_resource = api.bk_cmsi.send_weixin

    def _build_params(self) -> dict:
        if not AuditBkApiResource.use_multi_tenant_mode():
            # 旧 ESB 统一接口：消息体使用 data 字段
            return {
                "receiver__username": self.receivers,
                "data": {
                    "heading": self.title,
                    "message": self.content.to_string(),
                    **self.configs,
                },
            }

        # v1 多租户接口：消息体使用 message_data 字段，agentid/corpsecret 置于顶层
        top_level = {key: self.configs.pop(key) for key in _WEIXIN_TOP_LEVEL_KEYS if key in self.configs}
        return {
            "receiver__username": self.receivers,
            "message_data": {
                "heading": self.title,
                "message": self.content.to_string(),
                **self.configs,
            },
            **top_level,
        }
