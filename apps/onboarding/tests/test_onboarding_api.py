from datetime import date, timedelta

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.employees.models import Employee
from apps.onboarding.models import OnboardingItem, ViewedOnboardingItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def today():
    return date(2026, 7, 1)


@pytest.fixture
def freeze_onboarding_today(mocker, today):
    return mocker.patch(
        "apps.onboarding.selectors.timezone.localdate",
        return_value=today,
    )


def create_employee(
    django_user_model,
    *,
    login: str = "employee",
    email: str = "employee@example.com",
    hired_at: date | None = date(2026, 1, 10),
) -> Employee:
    user = django_user_model.objects.create_user(
        username=login,
        email=email,
        password="password",
    )

    return Employee.objects.create(
        user=user,
        email=email,
        login=login,
        first_name="First",
        last_name="Last",
        hired_at=hired_at,
    )


def create_onboarding_item(
    *,
    code: str = "welcome",
    title: str = "Welcome",
    release_date: date,
    active: bool = True,
) -> OnboardingItem:
    return OnboardingItem.objects.create(
        code=code,
        title=title,
        body="<p>Welcome to IntraCore.</p>",
        release_date=release_date,
        active=active,
    )


def test_eligible_employee_sees_onboarding(
    api_client,
    django_user_model,
    today,
    freeze_onboarding_today,
):
    employee = create_employee(django_user_model)
    item = create_onboarding_item(release_date=today - timedelta(days=5))
    api_client.force_authenticate(user=employee.user)

    response = api_client.get(reverse("onboarding-available"))

    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    assert [result["code"] for result in results] == [item.code]


def test_employee_hired_after_release_does_not_see_onboarding(
    api_client,
    django_user_model,
    today,
    freeze_onboarding_today,
):
    employee = create_employee(
        django_user_model,
        hired_at=today - timedelta(days=1),
    )
    create_onboarding_item(release_date=today - timedelta(days=10))
    api_client.force_authenticate(user=employee.user)

    response = api_client.get(reverse("onboarding-available"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["results"] == []


def test_onboarding_older_than_one_month_is_hidden(
    api_client,
    django_user_model,
    today,
    freeze_onboarding_today,
):
    employee = create_employee(django_user_model)
    create_onboarding_item(release_date=today - timedelta(days=32))
    api_client.force_authenticate(user=employee.user)

    response = api_client.get(reverse("onboarding-available"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["results"] == []


def test_viewed_onboarding_is_hidden(
    api_client,
    django_user_model,
    today,
    freeze_onboarding_today,
):
    employee = create_employee(django_user_model)
    item = create_onboarding_item(release_date=today - timedelta(days=5))
    ViewedOnboardingItem.objects.create(employee=employee, onboarding_item=item)
    api_client.force_authenticate(user=employee.user)

    response = api_client.get(reverse("onboarding-available"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["results"] == []


def test_mark_onboarding_as_viewed_is_idempotent(
    api_client,
    django_user_model,
    today,
    freeze_onboarding_today,
):
    employee = create_employee(django_user_model)
    item = create_onboarding_item(release_date=today - timedelta(days=5))
    api_client.force_authenticate(user=employee.user)

    first_response = api_client.post(
        reverse("onboarding-viewed", kwargs={"code": item.code}),
    )
    second_response = api_client.post(
        reverse("onboarding-viewed", kwargs={"code": item.code}),
    )

    assert first_response.status_code == status.HTTP_204_NO_CONTENT
    assert second_response.status_code == status.HTTP_204_NO_CONTENT
    assert (
        ViewedOnboardingItem.objects.filter(
            employee=employee,
            onboarding_item=item,
        ).count()
        == 1
    )


def test_inactive_onboarding_is_hidden(
    api_client,
    django_user_model,
    today,
    freeze_onboarding_today,
):
    employee = create_employee(django_user_model)
    create_onboarding_item(
        release_date=today - timedelta(days=5),
        active=False,
    )
    api_client.force_authenticate(user=employee.user)

    response = api_client.get(reverse("onboarding-available"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["results"] == []


def test_anonymous_user_cannot_read_onboarding(api_client):
    response = api_client.get(reverse("onboarding-available"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_invalid_onboarding_code_returns_404(
    api_client,
    django_user_model,
    freeze_onboarding_today,
):
    employee = create_employee(django_user_model)
    api_client.force_authenticate(user=employee.user)

    response = api_client.post(
        reverse("onboarding-viewed", kwargs={"code": "missing"}),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
