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
from django.utils.translation.trans_null import gettext_lazy

from apps.exceptions import CoreException


class ToolException(CoreException):
    MODULE_CODE = CoreException.Modules.TOOL


class DataSearchSimpleModeNotSupportedError(ToolException):
    MESSAGE = gettext_lazy("当前暂不支持 '简易模式'(simple) 的数据查询工具")
    ERROR_CODE = "001"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class ToolConfigException(ToolException):
    MESSAGE = gettext_lazy("Tool config error")
    ERROR_CODE = "002"


class DataSearchTablePermission(ToolException):
    STATUS_CODE = 403
    ERROR_CODE = "003"
    MESSAGE = gettext_lazy("用户{user}没有权限访问数据源{data_source}")

    def __init__(self, user, data_source, *args, **kwargs):
        self.MESSAGE = self.MESSAGE.format(user=user, data_source=data_source)
        super().__init__(*args, **kwargs)
