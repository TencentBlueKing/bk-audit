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
from django.utils.translation import gettext
from rest_framework.permissions import BasePermission

from apps.feature.constants import FeatureTypeChoices
from apps.feature.handlers import FeatureHandler
from core.exceptions import PermissionException, ValidationError
from core.models import get_request_username
from services.web.common.caller_permission import should_skip_permission_from
from services.web.common.constants import BindingResourceType
from services.web.common.scope_permission import ScopeInstancePermission
from services.web.scene.constants import PanelStatus
from services.web.tool.exceptions import BkVisionSearchPermissionProhibited
from services.web.tool.models import Tool


class CallerContextPermission(BasePermission):
    """调用方资源上下文权限：命中且有权限则整体放行"""

    def has_permission(self, request, view):
        username = get_request_username()
        return should_skip_permission_from(request, username)


class UseToolPermission(ScopeInstancePermission):
    """检查用户是否拥有使用工具的权限（含启停态与管理员例外）。"""

    def __init__(self, *args, **kwargs):
        super().__init__(
            resource_type=BindingResourceType.TOOL,
            status_getter=self._get_tool_status,
            published_status=PanelStatus.PUBLISHED,
            *args,
            **kwargs,
        )

    @staticmethod
    def _get_tool_status(tool_uid: str):
        tool = Tool.last_version_tool(uid=tool_uid)
        return tool.status if tool else None

    def has_permission(self, request, view) -> bool:
        """工具不存在、未上架、场景停用和不可见都返回 400，不带申请链接。"""

        resource_id = str(self._get_instance_id(request, view))
        if Tool.last_version_tool(uid=resource_id) is None:
            raise ValidationError(message=gettext("工具不存在，联系场景管理员"))
        if not self._is_scene_binding_enabled(resource_id):
            raise ValidationError(message=gettext("绑定场景停用或被删除，联系场景管理员"))
        username = get_request_username()
        if not self._is_resource_manager_exception(username, resource_id) and not self._is_resource_published(
            resource_id
        ):
            raise ValidationError(message=gettext("工具未上架，联系场景管理员"))
        try:
            return super().has_permission(request, view)
        except PermissionException as exc:
            reason = str(exc.args[0] if exc.args else exc.message or "").strip().rstrip("。；;，, ")
            raise ValidationError(message=gettext("%(reason)s，联系场景管理员") % {"reason": reason}) from exc


def check_bkvision_share_permission(user_id, share_uid) -> bool:
    """检查bkvision分享权限（受特性开关控制）"""
    if not FeatureHandler(FeatureTypeChoices.CHECK_BKVISION_SHARE_PERMISSION).check():
        return True
    result = api.bk_vision.check_share_auth(
        username=user_id,
        share_uid=share_uid,
    )
    check_result = result.get("check_result")
    if not check_result:
        raise BkVisionSearchPermissionProhibited(user_id, share_uid)
    return True
