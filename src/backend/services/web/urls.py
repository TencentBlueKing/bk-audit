from django.urls import include, path

urlpatterns = [
    path("", include("services.web.entry.urls")),
    path("api/v1/", include("services.web.analyze.urls")),
    path("api/v1/databus/", include("services.web.databus.urls")),
    path("api/v1/esquery/", include("services.web.esquery.urls")),
    path("api/v1/", include("services.web.strategy_v2.urls")),
    path("api/v1/", include("services.web.risk.urls")),
    path("api/v1/", include("services.web.version.urls")),
    path("api/v1/vision/", include("services.web.vision.urls")),
]
