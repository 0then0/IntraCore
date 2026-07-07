from apps.common.views import HealthView
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", HealthView.as_view(), name="health"),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[AllowAny]),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            permission_classes=[AllowAny],
            url_name="schema",
        ),
        name="swagger-ui",
    ),
    path("api/", include("apps.employees.urls")),
    path("api/org/", include("apps.org.urls")),
]
