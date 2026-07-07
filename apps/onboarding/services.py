from django.db import transaction

from apps.onboarding.models import ViewedOnboardingItem
from apps.onboarding.selectors import get_eligible_onboarding_item


@transaction.atomic
def mark_onboarding_item_viewed(employee, code: str) -> None:
    onboarding_item = get_eligible_onboarding_item(employee, code)

    ViewedOnboardingItem.objects.get_or_create(
        employee=employee,
        onboarding_item=onboarding_item,
    )
