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

from bk_resource.routers import ResourceRouter
from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.conf.urls import include
from django.urls import path, re_path

from apps.meta.constants import SensitiveResourceTypeEnum
from apps.meta.models import Action, ResourceType
from apps.meta.provider.sensitive_obj import SensitiveObjResourceProvider
from apps.meta.provider.system import SystemResourceProvider
from apps.meta.provider.tag import TagResourceProvider
from apps.notice.provider import NoticeGroupResourceProvider
from apps.permission import views
from apps.permission.dispatcher import BkAuditResourceApiDispatcher
from apps.permission.handlers.permission import Permission

try:
    from services.web.strategy_v2.provider import (
        LinkTableProvider,
        StrategyResourceProvider,
    )
except (RuntimeError, ImportError):
    StrategyResourceProvider = None
    LinkTableProvider = None

try:
    from services.web.risk.provider import RiskResourceProvider
except (RuntimeError, ImportError):
    RiskResourceProvider = None

try:
    from services.web.vision.providers import PanelResourceProvider
except (RuntimeError, ImportError):
    PanelResourceProvider = None

try:
    from services.web.tool.providers import ToolResourceProvider
except (RuntimeError, ImportError):
    ToolResourceProvider = None

resources_dispatcher = BkAuditResourceApiDispatcher(Permission.get_iam_client(), settings.BK_IAM_SYSTEM_ID)
resources_dispatcher.register("system", SystemResourceProvider())
resources_dispatcher.register("tag", TagResourceProvider())
resources_dispatcher.register(
    "sensitive_action", SensitiveObjResourceProvider(SensitiveResourceTypeEnum.ACTION.value, Action)
)
resources_dispatcher.register(
    "sensitive_resource_type",
    SensitiveObjResourceProvider(SensitiveResourceTypeEnum.RESOURCE.value, ResourceType),
)
resources_dispatcher.register("notice_group", NoticeGroupResourceProvider())

if StrategyResourceProvider is not None:
    resources_dispatcher.register("strategy", StrategyResourceProvider())

if RiskResourceProvider is not None:
    resources_dispatcher.register("risk", RiskResourceProvider())

if PanelResourceProvider is not None:
    resources_dispatcher.register("panel", PanelResourceProvider())

if ToolResourceProvider is not None:
    resources_dispatcher.register("tool", ToolResourceProvider())

if LinkTableProvider is not None:
    resources_dispatcher.register("link_table", LinkTableProvider())

router = ResourceRouter()
router.register_module(views)

urlpatterns = [
    re_path(r"namespaces/(?P<namespace>[\w\-]+)/", include(router.urls)),
    path("resources/", resources_dispatcher.as_view([login_exempt])),
]
