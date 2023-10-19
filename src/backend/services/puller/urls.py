from django.urls import include, path

urlpatterns = [
    path("api/v1/resources/", include("services.puller.puller.urls")),
]
