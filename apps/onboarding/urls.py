from django.urls import path

from apps.onboarding.views import (
    OnboardingAvailableListView,
    OnboardingViewedView,
)

urlpatterns = [
    path(
        "onboarding/available/",
        OnboardingAvailableListView.as_view(),
        name="onboarding-available",
    ),
    path(
        "onboarding/<slug:code>/viewed/",
        OnboardingViewedView.as_view(),
        name="onboarding-viewed",
    ),
]
