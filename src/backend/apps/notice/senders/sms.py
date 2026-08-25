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

from apps.notice.constants import MsgType
from apps.notice.senders.base import Sender
from core.bk_api_base import AuditBkApiResource


class SMSSender(Sender):
    """
    发送短信消息
    """

    api_resource = api.bk_cmsi.send_msg

    def _build_params(self) -> dict:
        if not AuditBkApiResource.use_muti_tenant_mode():
            # 旧 ESB 统一接口：需指定 msg_type 与 title
            return {
                "msg_type": MsgType.SMS.value,
                "receiver__username": self.receivers,
                "title": self.title,
                "content": self.content.to_string(),
                **self.configs,
            }

        # v1 多租户接口：使用独立的 send_sms 端点，无需 msg_type/title
        return {
            "receiver__username": self.receivers,
            "content": self.content.to_string(),
            **self.configs,
        }
