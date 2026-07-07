from datetime import date

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.employees.models import Employee
from apps.employees.tasks import sync_employee_from_hr_task

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def create_user(django_user_model, *, username: str, is_staff: bool = False):
    return django_user_model.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="password",
        is_staff=is_staff,
    )


def create_employee(
    django_user_model,
    *,
    login: str,
    is_staff: bool = False,
    external_id: str | None = "hr-1",
) -> Employee:
    user = create_user(django_user_model, username=login, is_staff=is_staff)

    return Employee.objects.create(
        user=user,
        external_id=external_id,
        email=f"{login}@example.com",
        login=login,
        first_name="First",
        last_name="Last",
        hired_at=date(2020, 1, 10),
    )


def hr_sync_url(employee: Employee) -> str:
    return reverse(
        "admin-employee-hr-sync",
        kwargs={"id": employee.employee_uuid},
    )


def test_anonymous_user_cannot_queue_hr_sync(api_client, django_user_model):
    employee = create_employee(django_user_model, login="employee")

    response = api_client.post(hr_sync_url(employee))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_non_staff_user_cannot_queue_hr_sync(api_client, django_user_model):
    employee = create_employee(django_user_model, login="employee")
    api_client.force_authenticate(user=employee.user)

    response = api_client.post(hr_sync_url(employee))

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_hr_sync_returns_503_when_flag_disabled(
    api_client,
    django_user_model,
    settings,
    mocker,
):
    settings.HR_SYNC_ENABLED = False
    admin_employee = create_employee(
        django_user_model,
        login="admin",
        is_staff=True,
        external_id="admin-hr-id",
    )
    employee = create_employee(django_user_model, login="employee")
    delay = mocker.patch.object(sync_employee_from_hr_task, "delay")
    api_client.force_authenticate(user=admin_employee.user)

    response = api_client.post(hr_sync_url(employee))

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["code"] == "hr_sync_disabled"
    delay.assert_not_called()


def test_admin_hr_sync_requires_external_id(
    api_client,
    django_user_model,
    settings,
    mocker,
):
    settings.HR_SYNC_ENABLED = True
    admin_employee = create_employee(
        django_user_model,
        login="admin",
        is_staff=True,
        external_id="admin-hr-id",
    )
    employee = create_employee(
        django_user_model,
        login="employee",
        external_id=None,
    )
    delay = mocker.patch.object(sync_employee_from_hr_task, "delay")
    api_client.force_authenticate(user=admin_employee.user)

    response = api_client.post(hr_sync_url(employee))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["code"] == "employee_external_id_missing"
    delay.assert_not_called()


def test_admin_can_queue_hr_sync(
    api_client,
    django_user_model,
    settings,
    mocker,
    django_capture_on_commit_callbacks,
):
    settings.HR_SYNC_ENABLED = True
    admin_employee = create_employee(
        django_user_model,
        login="admin",
        is_staff=True,
        external_id="admin-hr-id",
    )
    employee = create_employee(django_user_model, login="employee")
    delay = mocker.patch.object(sync_employee_from_hr_task, "delay")
    api_client.force_authenticate(user=admin_employee.user)

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(hr_sync_url(employee))

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == {
        "status": "queued",
        "employee_id": str(employee.employee_uuid),
    }
    delay.assert_called_once_with(employee.pk)


def test_openapi_schema_contains_hr_sync_path(api_client):
    response = api_client.get(reverse("schema"))

    assert response.status_code == status.HTTP_200_OK
    schema = response.content.decode()
    assert "/api/admin/employees/{id}/hr-sync/" in schema
