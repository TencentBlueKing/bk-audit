from django.urls import include, path

urlpatterns = [
    path("", include("services.web.entry.urls")),
    path("api/v1/", include("services.web.analyze.urls")),
    path("api/v1/databus/", include("services.web.databus.urls")),
    path("api/v1/query/", include("services.web.query.urls")),
    path("api/v1/log_subscription/", include("services.web.log_subscription.urls")),
    path("api/v1/", include("services.web.strategy_v2.urls")),
    path("api/v1/", include("services.web.risk.urls")),
    path("api/v1/", include("services.web.version.urls")),
    path("bkvision/api/v1/", include("services.web.vision.urls")),
    path("api/v1/", include("services.web.tool.urls")),
    path("api/v1/", include("services.web.blob_storage.urls")),
]
