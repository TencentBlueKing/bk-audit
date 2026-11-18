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
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

audit-meta 工具集的受控异常：对外 2927xxx 领域错误码。

权限拒绝不在此处定义：沿用平台 IAM PermissionException（403 + 权限申请数据），
与日志工具的用户态鉴权行为保持一致。
"""

from django.utils.translation import gettext_lazy

from apps.exceptions import CoreException


class MetaToolException(CoreException):
    """audit-meta 工具异常基类，公开消息不能由底层异常覆盖。"""

    MODULE_CODE = "27"

    def __init__(self, *args, **kwargs):
        # 元数据查询细节和底层服务异常只允许留在日志上下文，不能进入对外响应。
        super().__init__(message=self.MESSAGE)


class SystemNotAccessible(MetaToolException):
    """目标系统不存在或不属于当前命名空间，不能作为探索对象。"""

    ERROR_CODE = "001"
    STATUS_CODE = 400
    MESSAGE = gettext_lazy("目标系统不存在或不可访问，请使用系统列表返回的 system_id")


class MetaQueryFailed(MetaToolException):
    """元数据查询失败；底层异常收敛为不泄露细节的领域错误。"""

    ERROR_CODE = "002"
    STATUS_CODE = 502
    MESSAGE = gettext_lazy("元数据查询失败，请稍后重试")
