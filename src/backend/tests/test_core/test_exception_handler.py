"""公共 HTTP 异常分类：参数错误不应被当作服务执行失败。"""

from unittest import TestCase

from bk_resource import Resource
from bk_resource.exceptions import ValidateException
from django.conf import settings
from django.utils.module_loading import import_string
from rest_framework import serializers

from core.exceptions import ValidationError


class RequestExceptionHandlerTest(TestCase):
    def test_resource_response_validation_remains_500(self):
        """SDK 响应校验复用相同异常类，不能误判为客户端参数错误。"""

        class ResultSerializer(serializers.Serializer):
            count = serializers.IntegerField()

        class InvalidResponseResource(Resource):
            ResponseSerializer = ResultSerializer

            def perform_request(self, validated_request_data):
                """模拟服务返回不符合响应协议的数据。"""
                return {"count": "invalid"}

        handler = import_string(settings.REST_FRAMEWORK["EXCEPTION_HANDLER"])
        try:
            InvalidResponseResource().request({})
        except ValidateException as error:
            response = handler(error, {})
        else:
            self.fail("SDK 应拒绝非法响应")
        self.assertEqual(response.status_code, 500)

    def test_parameter_exceptions_return_400(self):
        """SDK 和项目参数异常均保留公开错误码并返回 400。"""
        handler = import_string(settings.REST_FRAMEWORK["EXCEPTION_HANDLER"])
        for error in (ValidateException("invalid parameter"), ValidationError("invalid scope")):
            with self.subTest(error=type(error).__name__):
                response = handler(error, {})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["code"], error.code)

    def test_unexpected_exception_remains_500(self):
        """未知执行错误不能被整体降级成参数错误。"""
        handler = import_string(settings.REST_FRAMEWORK["EXCEPTION_HANDLER"])
        response = handler(RuntimeError("execution failed"), {})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["code"], 500)
