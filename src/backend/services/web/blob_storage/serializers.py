from django.utils.translation import gettext_lazy
from rest_framework import serializers


class UploadRequestSerializer(serializers.Serializer):
    """附件上传请求序列化器"""

    files = serializers.ListSerializer(child=serializers.FileField(label=gettext_lazy("附件")), required=False)


class ImageUploadResponseSerializer(serializers.Serializer):
    """图片上传响应序列化器"""

    url = serializers.CharField(label=gettext_lazy("图片URL"))
    md5 = serializers.CharField(label=gettext_lazy("附件MD5"))
    origin_name = serializers.CharField(label=gettext_lazy("附件名称"))
    size = serializers.IntegerField(label=gettext_lazy("附件大小"))
