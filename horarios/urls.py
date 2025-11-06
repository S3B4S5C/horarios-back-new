from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path("admin/", admin.site.urls),

    # OpenAPI schema & UIs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # Tu API
    path("api/users/", include("users.urls")),
    path("api/academics/", include("academics.urls")),
    path("api/facilities/", include("facilities.urls")),
    path("api/scheduling/", include("scheduling.urls")),
    path("api/notifications/", include("notifications.urls")),
]
