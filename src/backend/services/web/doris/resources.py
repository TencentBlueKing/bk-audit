import abc
from typing import List

from bk_resource import Resource
from blueapps.utils.request_provider import get_local_request
from django.utils.translation import gettext_lazy as _lazy

from apps.audit.resources import AuditMixinResource
from services.web.doris.constants import (
    IMAGE_UPLOAD_DEFAULT_DIR,
    IMAGE_UPLOAD_SIZE_LIMIT,
    IMAGE_UPLOAD_SUFFIX_LIST,
)
from services.web.doris.serializers import (
    ImageUploadResponseSerializer,
    UploadRequestSerializer,
)
from services.web.doris.utils.upload import FileUpload


class DorisBase(AuditMixinResource, abc.ABC):
    tags = ["doris"]


class UploadResource(FileUpload, Resource, abc.ABC):
    RequestSerializer = UploadRequestSerializer
    many_response_data = True

    def update_files(self, validated_request_data: dict) -> List[dict]:
        """上传文件"""
        request = get_local_request()
        files = validated_request_data.get("files") or request.FILES
        if not files:
            return []
        return self.store_files(files)


class ImageUploadResource(DorisBase, UploadResource):
    name = _lazy("图片上传")
    ResponseSerializer = ImageUploadResponseSerializer
    FILE_UPLOAD_SUFFIX_LIST = IMAGE_UPLOAD_SUFFIX_LIST
    FILE_UPLOAD_SIZE_LIMIT = IMAGE_UPLOAD_SIZE_LIMIT
    FILE_UPLOAD_DEFAULT_DIR = IMAGE_UPLOAD_DEFAULT_DIR

    def perform_request(self, validated_request_data):
        return [
            {
                "url": meta["url"],
                "md5": meta["md5"],
                "origin_name": meta["origin_name"],
                "size": meta["size"],
            }
            for meta in self.update_files(validated_request_data)
        ]
