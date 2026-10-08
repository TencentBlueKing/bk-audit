"""平台 HTTP 异常适配。

bk_resource 的参数校验异常不继承 BlueException，需显式映射为客户端错误。
其余异常沿用 blueapps 的响应信封、权限错误及诊断日志。
"""

from traceback import walk_tb

from bk_resource import Resource
from bk_resource.exceptions import ValidateException
from blueapps.contrib.drf.exception import custom_exception_handler
from rest_framework import status
from rest_framework.response import Response


def exception_handler(exc, context):
    """将 SDK 请求参数校验失败返回为 400，其余委托既有处理器。"""
    if isinstance(exc, ValidateException):
        # SDK 请求、响应校验共用异常类；响应协议错误仍属于服务故障。
        if any(frame.f_code is Resource.validate_response_data.__code__ for frame, _ in walk_tb(exc.__traceback__)):
            return custom_exception_handler(exc, context)
        return Response(
            {"code": exc.code, "message": str(exc), "data": getattr(exc, "data", None)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return custom_exception_handler(exc, context)
