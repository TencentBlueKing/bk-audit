# -*- coding: utf-8 -*-
from bk_resource.routers import ResourceRouter
from django.urls import include, path

from services.web.blob_storage import views

router = ResourceRouter()
router.register_module(views)

urlpatterns = [
    path("blob_storage/", include(router.urls)),
]
