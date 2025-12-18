# -*- coding: utf-8 -*-
from bk_resource import resource
from bk_resource.viewsets import ResourceRoute, ResourceViewSet


class UploadViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", resource.blob_storage.image_upload),
    ]
