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

from bk_audit.contrib.django.resources import AuditEvent
from bk_audit.contrib.django.resources import AuditMixinResource as _AuditMixinResource


class AuditMixinResource(_AuditMixinResource, abc.ABC):
    def _init_audit_event(self, request_data=None, **kwargs) -> AuditEvent:
        event = super()._init_audit_event(request_data=request_data, **kwargs)
        event["extend_data"]["request_data"] = request_data
        return event
