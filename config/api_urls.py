from apps.common.views import HealthView
from django.urls import include, path

api_urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("api/", include("apps.employees.urls")),
    path("api/", include("apps.legal.urls")),
    path("api/", include("apps.onboarding.urls")),
    path("api/org/", include("apps.org.urls")),
]

urlpatterns = api_urlpatterns
