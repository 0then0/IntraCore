from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.employees.models import Employee
from apps.employees.services import sync_employee_from_hr

pytestmark = pytest.mark.django_db


class FakeHrClient:
    def __init__(self, payload):
        self.payload = payload

    def get_employee(self, external_id: str) -> dict:
        return self.payload


@pytest.fixture
def api_client():
    return APIClient()


def create_employee(
    django_user_model,
    *,
    login: str = "employee",
    external_id: str | None = None,
    education: str = "",
    city: str = "",
    add_location: str = "",
    location_city: str = "",
    location: str = "",
) -> Employee:
    user = django_user_model.objects.create_user(
        username=login,
        email=f"{login}@example.com",
        password="password",
    )

    if external_id is None:
        external_id = f"hr-{login}"

    return Employee.objects.create(
        user=user,
        external_id=external_id,
        email=f"{login}@example.com",
        login=login,
        first_name="First",
        last_name="Last",
        education=education,
        city=city,
        add_location=add_location,
        location_city=location_city,
        location=location,
        hired_at=date(2020, 1, 10),
    )


def test_education_accepts_2500_characters(django_user_model):
    employee = create_employee(
        django_user_model,
        education="a" * 2500,
    )

    employee.full_clean()


def test_education_rejects_2501_characters(django_user_model):
    employee = create_employee(django_user_model)
    employee.education = "a" * 2501

    with pytest.raises(ValidationError) as error:
        employee.full_clean()

    assert "education" in error.value.message_dict


@pytest.mark.parametrize(
    ("field_values", "expected_city"),
    [
        (
            {
                "add_location": "Add Location",
                "location_city": "City",
                "location": "Raw",
            },
            "Add Location",
        ),
        ({"location_city": "City", "location": "Raw", "city": "Manual"}, "City"),
        ({"location": "Raw", "city": "Manual"}, "Raw"),
        ({"city": "Manual"}, "Manual"),
    ],
)
def test_employee_effective_city_fallback_order(
    django_user_model,
    field_values,
    expected_city,
):
    employee = create_employee(django_user_model, **field_values)

    assert employee.effective_city == expected_city


def test_profile_api_returns_city_fallback(api_client, django_user_model):
    employee = create_employee(
        django_user_model,
        city="Manual",
        location="Raw",
        location_city="City",
        add_location="Add Location",
    )
    api_client.force_authenticate(user=employee.user)

    response = api_client.get(reverse("profile-me"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["city"] == "Add Location"


def test_profile_api_accepts_2500_character_education(api_client, django_user_model):
    employee = create_employee(django_user_model)
    api_client.force_authenticate(user=employee.user)

    response = api_client.patch(
        reverse("profile-me"),
        {"education": "a" * 2500},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    employee.refresh_from_db()
    assert employee.education == "a" * 2500


def test_profile_api_rejects_2501_character_education(api_client, django_user_model):
    employee = create_employee(django_user_model)
    api_client.force_authenticate(user=employee.user)

    response = api_client.patch(
        reverse("profile-me"),
        {"education": "a" * 2501},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "education" in response.json()


def test_org_employee_list_returns_city_fallback(api_client, django_user_model):
    viewer = create_employee(django_user_model, login="viewer")
    employee = create_employee(
        django_user_model,
        login="employee",
        city="Manual",
        location="Raw",
        location_city="City",
    )
    api_client.force_authenticate(user=viewer.user)

    response = api_client.get(
        reverse("org-employee-list"),
        {"search": employee.email},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["results"][0]["city"] == "City"


def test_hr_sync_updates_location_source_fields(django_user_model, settings):
    settings.HR_SYNC_ENABLED = True
    employee = create_employee(django_user_model, city="Manual")
    hr_client = FakeHrClient(
        {
            "external_id": employee.external_id,
            "add_location": "",
            "location_city": "HR City",
            "location": "HR Raw",
        },
    )

    sync_employee_from_hr(employee, hr_client=hr_client)

    employee.refresh_from_db()
    assert employee.add_location == ""
    assert employee.location_city == "HR City"
    assert employee.location == "HR Raw"
    assert employee.effective_city == "HR City"
