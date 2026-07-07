from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.onboarding.models import OnboardingItem, ViewedOnboardingItem

ONBOARDING_VISIBLE_DAYS = 31


def eligible_onboarding_items_queryset(employee, *, today=None):
    today = today or timezone.localdate()
    oldest_release_date = today - timedelta(days=ONBOARDING_VISIBLE_DAYS)

    queryset = OnboardingItem.objects.filter(
        active=True,
        release_date__gte=oldest_release_date,
        release_date__lte=today,
    )

    if employee.hired_at:
        queryset = queryset.filter(release_date__gte=employee.hired_at)

    return queryset.order_by("-release_date", "title")


def available_onboarding_items_queryset(employee, *, today=None):
    viewed_item_ids = ViewedOnboardingItem.objects.filter(
        employee=employee,
    ).values("onboarding_item_id")

    return eligible_onboarding_items_queryset(
        employee,
        today=today,
    ).exclude(id__in=viewed_item_ids)


def get_eligible_onboarding_item(employee, code: str) -> OnboardingItem:
    return get_object_or_404(
        eligible_onboarding_items_queryset(employee),
        code=code,
    )
