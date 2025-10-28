import abc
from typing import List

from bk_resource import Resource
from blueapps.utils.request_provider import get_local_request
from django.utils.translation import gettext_lazy as _lazy

from apps.audit.resources import AuditMixinResource
from services.web.blob_storage.constants import (
    IMAGE_UPLOAD_DEFAULT_DIR,
    IMAGE_UPLOAD_SIZE_LIMIT,
    IMAGE_UPLOAD_SUFFIX_LIST,
)
from services.web.blob_storage.serializers import (
    ImageUploadResponseSerializer,
    UploadRequestSerializer,
)
from services.web.blob_storage.utils.upload import FileUpload


class BlobStorageBase(AuditMixinResource, abc.ABC):
    tags = ["blob_storage"]


class UploadResource(FileUpload, Resource, abc.ABC):
    RequestSerializer = UploadRequestSerializer
    many_response_data = True

    def update_files(self) -> List[dict]:
        """上传文件"""
        request = get_local_request()
        files = request.FILES
        if not files:
            return []
        return self.store_files(files)


class ImageUploadResource(BlobStorageBase, UploadResource):
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
            for meta in self.update_files()
        ]
