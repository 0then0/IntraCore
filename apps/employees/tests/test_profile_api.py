from datetime import date
from uuid import uuid4

import pytest
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.employees.models import Employee
from apps.org.models import Department

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def department():
    return Department.objects.create(code="engineering", name="Engineering")


def create_employee(
    django_user_model,
    *,
    login: str,
    email: str,
    department: Department | None = None,
    manager: Employee | None = None,
    is_staff: bool = False,
    phone: str = "+79990000000",
    is_phone_visible: bool = False,
    birthdate: date | None = date(1990, 5, 20),
    is_birthdate_visible: bool = False,
    external_id: str | None = None,
) -> Employee:
    user = django_user_model.objects.create_user(
        username=login,
        email=email,
        password="password",
        is_staff=is_staff,
    )

    return Employee.objects.create(
        user=user,
        email=email,
        login=login,
        first_name="First",
        last_name="Last",
        department=department,
        manager=manager,
        phone=phone,
        is_phone_visible=is_phone_visible,
        birthdate=birthdate,
        is_birthdate_visible=is_birthdate_visible,
        external_id=external_id,
        hired_at=date(2020, 1, 10),
    )


def employee_detail_url(employee: Employee) -> str:
    return reverse("employee-detail", kwargs={"id": employee.employee_uuid})


def admin_employee_detail_url(employee: Employee) -> str:
    return reverse("admin-employee-detail", kwargs={"id": employee.employee_uuid})


def test_user_can_read_own_profile_with_hidden_fields(
    api_client,
    django_user_model,
    department,
):
    employee = create_employee(
        django_user_model,
        login="owner",
        email="owner@example.com",
        department=department,
        external_id="hr-owner",
    )
    api_client.force_authenticate(user=employee.user)

    response = api_client.get(reverse("profile-me"))

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(employee.employee_uuid)
    assert data["external_id"] == "hr-owner"
    assert data["phone"] == "+79990000000"
    assert data["birthdate"] == "1990-05-20"
    assert data["department"] == {
        "code": "engineering",
        "name": "Engineering",
    }


def test_user_cannot_read_other_employee_hidden_phone(
    api_client,
    django_user_model,
):
    viewer = create_employee(
        django_user_model,
        login="viewer",
        email="viewer@example.com",
    )
    target = create_employee(
        django_user_model,
        login="target",
        email="target@example.com",
        phone="+79991112233",
        is_phone_visible=False,
    )
    api_client.force_authenticate(user=viewer.user)

    response = api_client.get(employee_detail_url(target))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["phone"] is None


def test_user_cannot_read_other_employee_hidden_birthdate(
    api_client,
    django_user_model,
):
    viewer = create_employee(
        django_user_model,
        login="viewer",
        email="viewer@example.com",
    )
    target = create_employee(
        django_user_model,
        login="target",
        email="target@example.com",
        birthdate=date(1985, 2, 14),
        is_birthdate_visible=False,
        external_id="hr-target",
    )
    api_client.force_authenticate(user=viewer.user)

    response = api_client.get(employee_detail_url(target))

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["birthdate"] is None
    assert data["external_id"] is None


def test_nested_manager_hidden_birthdate_is_not_inherited_from_profile_owner(
    api_client,
    django_user_model,
):
    manager = create_employee(
        django_user_model,
        login="manager",
        email="manager@example.com",
        birthdate=date(1975, 3, 1),
        is_birthdate_visible=False,
    )
    employee = create_employee(
        django_user_model,
        login="employee",
        email="employee@example.com",
        manager=manager,
        birthdate=date(1992, 8, 15),
        is_birthdate_visible=False,
    )
    api_client.force_authenticate(user=employee.user)

    response = api_client.get(reverse("profile-me"))

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["birthdate"] == "1992-08-15"
    assert data["manager"]["birthdate"] is None


def test_anonymous_user_cannot_read_private_profile(api_client):
    response = api_client.get(reverse("profile-me"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_anonymous_user_cannot_patch_private_profile(api_client):
    response = api_client.patch(
        reverse("profile-me"),
        {"about": "Hidden"},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_anonymous_user_cannot_read_employee_detail(api_client, django_user_model):
    employee = create_employee(
        django_user_model,
        login="employee",
        email="employee@example.com",
    )

    response = api_client.get(employee_detail_url(employee))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_anonymous_user_cannot_patch_admin_employee(api_client, django_user_model):
    employee = create_employee(
        django_user_model,
        login="employee",
        email="employee@example.com",
    )

    response = api_client.patch(
        admin_employee_detail_url(employee),
        {"position": "Lead Engineer"},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_non_existing_employee_returns_404(api_client, django_user_model):
    viewer = create_employee(
        django_user_model,
        login="viewer",
        email="viewer@example.com",
    )
    api_client.force_authenticate(user=viewer.user)

    response = api_client.get(
        reverse("employee-detail", kwargs={"id": uuid4()}),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_user_can_patch_safe_profile_fields(api_client, django_user_model):
    employee = create_employee(
        django_user_model,
        login="owner",
        email="owner@example.com",
    )
    api_client.force_authenticate(user=employee.user)

    response = api_client.patch(
        reverse("profile-me"),
        {
            "about": "Backend engineer",
            "city": "Moscow",
            "is_phone_visible": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    employee.refresh_from_db()
    assert employee.about == "Backend engineer"
    assert employee.city == "Moscow"
    assert employee.is_phone_visible is True


def test_user_can_send_empty_profile_patch(api_client, django_user_model):
    employee = create_employee(
        django_user_model,
        login="owner",
        email="owner@example.com",
    )
    api_client.force_authenticate(user=employee.user)

    response = api_client.patch(reverse("profile-me"), {}, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == str(employee.employee_uuid)


def test_user_patch_rejects_forbidden_fields(api_client, django_user_model):
    employee = create_employee(
        django_user_model,
        login="owner",
        email="owner@example.com",
    )
    api_client.force_authenticate(user=employee.user)

    response = api_client.patch(
        reverse("profile-me"),
        {"email": "changed@example.com"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.json()


def test_user_patch_rejects_non_object_payload(api_client, django_user_model):
    employee = create_employee(
        django_user_model,
        login="owner",
        email="owner@example.com",
    )
    api_client.force_authenticate(user=employee.user)

    response = api_client.patch(
        reverse("profile-me"),
        ["about"],
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.json()


def test_user_patch_rejects_invalid_birthdate(api_client, django_user_model):
    employee = create_employee(
        django_user_model,
        login="owner",
        email="owner@example.com",
    )
    api_client.force_authenticate(user=employee.user)

    response = api_client.patch(
        reverse("profile-me"),
        {"birthdate": "2999-01-01"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "birthdate" in response.json()


def test_user_patch_rejects_too_long_about(api_client, django_user_model):
    employee = create_employee(
        django_user_model,
        login="owner",
        email="owner@example.com",
    )
    api_client.force_authenticate(user=employee.user)

    response = api_client.patch(
        reverse("profile-me"),
        {"about": "a" * 2501},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "about" in response.json()


def test_non_staff_user_cannot_patch_admin_employee(
    api_client,
    django_user_model,
):
    employee = create_employee(
        django_user_model,
        login="employee",
        email="employee@example.com",
    )
    api_client.force_authenticate(user=employee.user)

    response = api_client.patch(
        admin_employee_detail_url(employee),
        {"position": "Lead Engineer"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_staff_user_can_patch_admin_employee(
    api_client,
    django_user_model,
    department,
):
    admin_employee = create_employee(
        django_user_model,
        login="admin",
        email="admin@example.com",
        is_staff=True,
    )
    manager = create_employee(
        django_user_model,
        login="manager",
        email="manager@example.com",
    )
    employee = create_employee(
        django_user_model,
        login="employee",
        email="employee@example.com",
        phone="+79995556677",
        is_phone_visible=False,
    )
    api_client.force_authenticate(user=admin_employee.user)

    response = api_client.patch(
        admin_employee_detail_url(employee),
        {
            "department": department.code,
            "manager": str(manager.employee_uuid),
            "position": "Lead Engineer",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    employee.refresh_from_db()
    data = response.json()
    assert employee.department == department
    assert employee.manager == manager
    assert employee.position == "Lead Engineer"
    assert data["manager"]["id"] == str(manager.employee_uuid)
    assert data["phone"] == "+79995556677"


def test_staff_user_cannot_set_employee_as_own_manager(
    api_client,
    django_user_model,
):
    admin_employee = create_employee(
        django_user_model,
        login="admin",
        email="admin@example.com",
        is_staff=True,
    )
    employee = create_employee(
        django_user_model,
        login="employee",
        email="employee@example.com",
    )
    api_client.force_authenticate(user=admin_employee.user)

    response = api_client.patch(
        admin_employee_detail_url(employee),
        {"manager": str(employee.employee_uuid)},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "manager" in response.json()


def test_admin_patch_maps_database_constraint_error(
    api_client,
    django_user_model,
    mocker,
):
    admin_employee = create_employee(
        django_user_model,
        login="admin",
        email="admin@example.com",
        is_staff=True,
    )
    employee = create_employee(
        django_user_model,
        login="employee",
        email="employee@example.com",
    )
    api_client.force_authenticate(user=admin_employee.user)
    mocker.patch.object(Employee, "save", side_effect=IntegrityError("duplicate key"))

    response = api_client.patch(
        admin_employee_detail_url(employee),
        {"email": "changed@example.com"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.json()


def test_openapi_schema_contains_profile_paths(api_client):
    response = api_client.get(reverse("schema"))

    assert response.status_code == status.HTTP_200_OK
    schema = response.content.decode()
    assert "/api/profile/me/" in schema
    assert "/api/employees/{id}/" in schema
    assert "/api/admin/employees/{id}/" in schema
