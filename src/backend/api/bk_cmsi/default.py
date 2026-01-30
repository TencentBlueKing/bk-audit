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

import requests
from bk_resource.exceptions import APIRequestError
from bk_resource.utils.logger import logger
from django.utils.translation import gettext_lazy

from api.base import CommonBkApiResource
from api.domains import BK_CMSI_API_URL


class CMSIResource(CommonBkApiResource, abc.ABC):
    base_url = BK_CMSI_API_URL
    module_name = "bk_cmsi"
    IS_STANDARD_FORMAT = False

    def parse_response(self, response: requests.Response) -> any:
        data = super().parse_response(response)
        if not data.get("result", True) and data.get("code") != 0:
            msg = data.get("message", "")
            logger.error(
                "【Module: %s】【Action: %s】get error：%s",
                self.module_name,
                self.action,
                msg,
                extra=dict(module_name=self.module_name, url=response.request.url),
            )
            raise APIRequestError(
                module_name=self.module_name,
                url=self.action,
                result=data,
            )
        return data


class GetMsgType(CMSIResource):
    name = gettext_lazy("获取消息类型")
    method = "GET"
    action = "/get_msg_type/"


class SendMail(CMSIResource):
    name = gettext_lazy("发送邮件")
    method = "POST"
    action = "/send_mail/"


class SendRtx(CMSIResource):
    name = gettext_lazy("发送企业微信")
    method = "POST"
    action = "/send_rtx/"


class SendVoice(CMSIResource):
    name = gettext_lazy("发送语音")
    method = "POST"
    action = "/send_voice_msg/"


class SendMsg(CMSIResource):
    name = gettext_lazy("发送消息")
    method = "POST"
    action = "/send_msg/"


class SendWeixin(CMSIResource):
    name = gettext_lazy("发送微信")
    method = "POST"
    action = "/send_weixin/"
