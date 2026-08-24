from unittest import mock

from django.conf import settings
from drf_spectacular.utils import PolymorphicProxySerializer
from rest_framework import serializers

from tests.base import TestCase


class EchoInput(serializers.Serializer):
    text = serializers.CharField(help_text="回显输入字段")


class PolymorphicProxySerializerTest(TestCase):
    """多态协议在应用启动注册完成后按首次解析结果生成。"""

    def test_project_does_not_override_schema_generator(self):
        self.assertNotIn("DEFAULT_GENERATOR_CLASS", settings.SPECTACULAR_SETTINGS)

    def test_polymorphic_proxy_uses_startup_mapping_once(self):
        mapping_factory = mock.Mock(return_value={"ECHO": EchoInput})
        proxy = PolymorphicProxySerializer(
            component_name="TestStartupMapping",
            serializers=mapping_factory,
            resource_type_field_name="message_type",
        )

        self.assertEqual(proxy.serializers, {"ECHO": EchoInput})
        self.assertEqual(proxy.serializers, {"ECHO": EchoInput})
        mapping_factory.assert_called_once_with()
