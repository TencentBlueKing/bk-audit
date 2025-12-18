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
import json
from typing import Dict, List

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger
from django.db import transaction

from apps.meta.constants import (
    SYSTEM_DIAGNOSIS_PUSH_RECIPIENTS_KEY,
    SYSTEM_DIAGNOSIS_PUSH_TEMPLATE_KEY,
    ConfigLevelChoices,
    SystemDiagnosisPushStatusEnum,
)
from apps.meta.exceptions import SystemDiagnosisPushTemplateEmpty, SystemRoleMemberEmpty
from apps.meta.models import GlobalMetaConfig, System, SystemDiagnosisConfig
from core.render import Jinja2Renderer
from core.utils.tools import is_product
from services.web.risk.constants import SECURITY_PERSON_KEY


class SystemDiagnosisPushHandler:
    """
    系统诊断推送
    """

    def __init__(self, system_id: str):
        self.jinja_render = Jinja2Renderer()
        self.system_id = system_id
        self.system = System.objects.get(system_id=system_id)

    @property
    def system_data(self) -> dict:
        """
        系统渲染数据
        """

        push_recipients: Dict[str, List[str]] = GlobalMetaConfig.get(
            config_key=SYSTEM_DIAGNOSIS_PUSH_RECIPIENTS_KEY,
            config_level=ConfigLevelChoices.NAMESPACE,
            instance_key=self.system.namespace,
            default={},
        )
        # 获取推送接收人
        if push_recipients.get(self.system_id):
            # 指定系统推送接收人
            recipient = push_recipients[self.system_id]
        else:
            # 默认推送接收人:系统管理员
            recipient: List[str] = self.system.managers_list
        if not is_product():
            recipient = GlobalMetaConfig.get(config_key=SECURITY_PERSON_KEY)
        if not recipient:
            raise SystemRoleMemberEmpty()
        return {
            "system_name": self.system.name,
            "recipient": recipient,
            "system_id": self.system_id,
            "system_diagnosis_extra": self.system.system_diagnosis_extra or {},
        }

    @property
    def push_config(self) -> dict:
        """
        获取推送配置(渲染后)
        """

        push_template = GlobalMetaConfig.get(
            SYSTEM_DIAGNOSIS_PUSH_TEMPLATE_KEY,
            config_level=ConfigLevelChoices.NAMESPACE,
            instance_key=self.system.namespace,
            default={},
        )
        if not push_template:
            raise SystemDiagnosisPushTemplateEmpty()
        render_str = self.jinja_render.jinja_render(push_template, self.system_data)
        return json.loads(render_str)

    def _update_or_create(self, push_params: dict) -> bool:
        """
        更新或创建系统诊断推送配置
        """

        system_diagnosis_config, _ = SystemDiagnosisConfig.objects.select_for_update().get_or_create(
            system_id=self.system_id
        )
        is_ok = False
        try:
            if system_diagnosis_config.push_uid:
                push_params["uid"] = system_diagnosis_config.push_uid
                result = api.bk_vision.update_report_strategy(push_params)
            else:
                result = api.bk_vision.create_report_strategy(push_params)
                system_diagnosis_config.push_uid = result["uid"]
            system_diagnosis_config.push_result = result
            system_diagnosis_config.push_status = result["status"]
            system_diagnosis_config.push_error_message = ""
            is_ok = True
        except APIRequestError as e:
            logger.error(f"[{self.__class__.__name__}] call bkvision api error: {e}")
            system_diagnosis_config.push_result = None
            system_diagnosis_config.push_status = SystemDiagnosisPushStatusEnum.FAILED.value
            system_diagnosis_config.push_error_message = str(e)
            is_ok = False
        finally:
            system_diagnosis_config.push_config = push_params
            system_diagnosis_config.save()
            return is_ok

    @transaction.atomic()
    def change_push_status(self, enable_push: bool) -> bool:
        """
        改变推送状态
        """

        push_config = self.push_config
        push_config["status"] = (
            SystemDiagnosisPushStatusEnum.PUSH.value if enable_push else SystemDiagnosisPushStatusEnum.PAUSE.value
        )
        is_ok = self._update_or_create(push_config)
        if is_ok:
            self.system.enable_system_diagnosis_push = enable_push
            self.system.save(update_fields=["enable_system_diagnosis_push"])
        return is_ok

    @transaction.atomic()
    def delete_push(self):
        """
        删除推送
        """

        system_diagnosis_config = SystemDiagnosisConfig.objects.filter(system_id=self.system_id).first()
        if not system_diagnosis_config or not system_diagnosis_config.push_uid:
            return
        uid = system_diagnosis_config.push_uid
        api.bk_vision.delete_report_strategy(uid=uid)
        system_diagnosis_config.delete()
        self.system.enable_system_diagnosis_push = False
        self.system.save(update_fields=["enable_system_diagnosis_push"])
