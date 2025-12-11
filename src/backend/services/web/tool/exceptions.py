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
from typing import Any

from django.utils.translation.trans_null import gettext_lazy

from apps.exceptions import CoreException
from services.web.tool.constants import FieldCategory


class ToolException(CoreException):
    MODULE_CODE = CoreException.Modules.TOOL


class DataSearchSimpleModeNotSupportedError(ToolException):
    MESSAGE = gettext_lazy("当前暂不支持 '简易模式'(simple) 的数据查询工具")
    STATUS_CODE = 400
    ERROR_CODE = "001"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class DataSearchTablePermission(ToolException):
    STATUS_CODE = 409
    ERROR_CODE = "003"
    MESSAGE = gettext_lazy("用户{user}没有权限访问数据源{data_source}")

    def __init__(self, user, data_source, *args, **kwargs):
        self.MESSAGE = self.MESSAGE.format(user=user, data_source=data_source)
        super().__init__(*args, **kwargs)


class InputVariableMissingError(ToolException):
    """
    输入变量缺失
    """

    STATUS_CODE = 400
    ERROR_CODE = "004"
    MESSAGE = gettext_lazy("输入变量“{var_name}”必填")

    def __init__(self, var_name: str, *args, **kwargs):
        self.MESSAGE = self.MESSAGE.format(var_name=var_name)
        super().__init__(*args, **kwargs)


class InputVariableValueError(ToolException):
    """
    用户提供的变量值错误的基类异常。
    """

    STATUS_CODE = 400
    ERROR_CODE = "005"
    MESSAGE = gettext_lazy("用户输入变量值无效")


class InvalidVariableFormatError(InputVariableValueError):
    """
    当变量值的格式不正确时抛出。
    (例如，无效的日期字符串，非数字的值)
    """

    ERROR_CODE = "006"
    MESSAGE = gettext_lazy("变量类型“{var_type}”的值“{value}”格式无效")

    def __init__(self, var_type: FieldCategory, value: Any, *args, **kwargs):
        self.MESSAGE = self.MESSAGE.format(var_type=var_type.label, value=value)
        super().__init__(*args, **kwargs)


class InvalidVariableStructureError(InputVariableValueError):
    """
    当变量值的结构不正确时抛出。
    (例如，期望一个列表，但收到了一个字符串)
    """

    ERROR_CODE = "007"
    MESSAGE = gettext_lazy("变量类型“{var_type}”的值结构无效: 期望“{expected_structure}”,但收到的是“{actual_type}”")

    def __init__(self, var_type: FieldCategory, expected_structure: str, value: Any, *args, **kwargs):
        actual_type = type(value).__name__
        self.MESSAGE = self.MESSAGE.format(
            var_type=var_type.label, expected_structure=expected_structure, actual_type=actual_type
        )
        super().__init__(*args, **kwargs)


class VariableHasNoParseFunction(ToolException):
    """
    变量没有解析函数
    """

    STATUS_CODE = 500
    ERROR_CODE = "008"
    MESSAGE = gettext_lazy("变量类型“{var_type}”没有解析函数")

    def __init__(self, var_type: FieldCategory, *args, **kwargs):
        self.MESSAGE = self.MESSAGE.format(var_type=var_type.label)
        super().__init__(*args, **kwargs)


class ParseVariableError(ToolException):
    """
    解析变量异常
    """

    STATUS_CODE = 500
    ERROR_CODE = "009"
    MESSAGE = gettext_lazy("解析变量类型“{var_type}”的值“{value}”异常,请联系系统管理员")

    def __init__(self, var_type: FieldCategory, value: str, *args, **kwargs):
        self.MESSAGE = self.MESSAGE.format(var_type=var_type.label, value=value)
        super().__init__(*args, **kwargs)


class BkbaseApiRequestError(ToolException):
    """
    bkbase api 请求异常
    """

    STATUS_CODE = 500
    ERROR_CODE = "010"
    MESSAGE = gettext_lazy("bkbase 查询异常;执行 SQL：{sql}")

    def __init__(self, sql: str, *args, **kwargs):
        self.MESSAGE = self.MESSAGE.format(sql=sql)
        super().__init__(*args, **kwargs)


class BkVisionSearchPermissionProhibited(ToolException):
    STATUS_CODE = 409
    ERROR_CODE = "011"
    MESSAGE = gettext_lazy("用户{user}没有权限访问嵌入图表{share_uid}")

    def __init__(self, user, share_uid, *args, **kwargs):
        self.MESSAGE = self.MESSAGE.format(user=user, share_uid=share_uid)
        super().__init__(*args, **kwargs)


class ToolDoesNotExist(ToolException):
    """
    工具不存在
    """

    STATUS_CODE = 404
    ERROR_CODE = "012"
    MESSAGE = gettext_lazy("工具不存在")


class ToolTypeNotSupport(ToolException):
    """
    工具类型不支持
    """

    STATUS_CODE = 400
    ERROR_CODE = "013"
    MESSAGE = gettext_lazy("工具类型不支持")


class ApiToolExecuteError(ToolException):
    """
    API 工具执行异常
    """

    STATUS_CODE = 400
    ERROR_CODE = "014"
    MESSAGE = gettext_lazy("请求第三方接口失败：[{status_code}] {detail}")

    def __init__(self, status_code: int, detail: str, *args, **kwargs):
        self.status_code = status_code
        self.detail = detail
        self.MESSAGE = self.MESSAGE.format(status_code=status_code, detail=detail)
        super().__init__(*args, **kwargs)
