from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.employees.models import Employee
from apps.employees.services import sync_employee_from_hr
from apps.integrations.exceptions import HrSyncDisabledError
from apps.org.models import Department

pytestmark = pytest.mark.django_db


class FakeHrClient:
    def __init__(self, payload):
        self.payload = payload
        self.called_with = None

    def get_employee(self, external_id: str) -> dict:
        self.called_with = external_id
        return self.payload


def create_employee(django_user_model, *, external_id: str | None = "hr-1"):
    user = django_user_model.objects.create_user(
        username="employee",
        email="employee@example.com",
        password="password",
    )

    return Employee.objects.create(
        user=user,
        external_id=external_id,
        email="employee@example.com",
        login="employee",
        first_name="First",
        last_name="Last",
        hired_at=date(2020, 1, 10),
    )


def test_sync_employee_from_hr_updates_employee(django_user_model, settings):
    settings.HR_SYNC_ENABLED = True
    department = Department.objects.create(code="engineering", name="Engineering")
    employee = create_employee(django_user_model)
    hr_client = FakeHrClient(
        {
            "external_id": "hr-1",
            "email": "synced@example.com",
            "login": "synced",
            "first_name": "Synced",
            "last_name": "Employee",
            "middle_name": "Middle",
            "position": "Backend Engineer",
            "department_code": department.code,
            "phone": "+79990001122",
            "telegram_username": "synced_employee",
            "city": "Moscow",
            "hired_at": "2021-02-03",
            "is_active": True,
        },
    )

    synced_employee = sync_employee_from_hr(employee, hr_client=hr_client)

    assert hr_client.called_with == "hr-1"
    synced_employee.refresh_from_db()
    assert synced_employee.email == "synced@example.com"
    assert synced_employee.login == "synced"
    assert synced_employee.first_name == "Synced"
    assert synced_employee.last_name == "Employee"
    assert synced_employee.department == department
    assert synced_employee.hired_at == date(2021, 2, 3)


def test_sync_employee_from_hr_does_not_call_client_when_flag_disabled(
    django_user_model,
    settings,
    mocker,
):
    settings.HR_SYNC_ENABLED = False
    employee = create_employee(django_user_model)
    hr_client = mocker.Mock()

    with pytest.raises(HrSyncDisabledError):
        sync_employee_from_hr(employee, hr_client=hr_client)

    hr_client.get_employee.assert_not_called()


def test_sync_employee_from_hr_requires_external_id(django_user_model, settings):
    settings.HR_SYNC_ENABLED = True
    employee = create_employee(django_user_model, external_id=None)
    hr_client = FakeHrClient({})

    with pytest.raises(ValidationError) as error:
        sync_employee_from_hr(employee, hr_client=hr_client)

    assert "external_id" in error.value.message_dict
    assert hr_client.called_with is None


def test_sync_employee_from_hr_rejects_mismatched_external_id(
    django_user_model,
    settings,
):
    settings.HR_SYNC_ENABLED = True
    employee = create_employee(django_user_model)
    hr_client = FakeHrClient({"external_id": "other-hr-id"})

    with pytest.raises(ValidationError) as error:
        sync_employee_from_hr(employee, hr_client=hr_client)

    assert "external_id" in error.value.message_dict


def test_sync_employee_from_hr_rejects_unknown_department(
    django_user_model,
    settings,
):
    settings.HR_SYNC_ENABLED = True
    employee = create_employee(django_user_model)
    hr_client = FakeHrClient(
        {
            "external_id": "hr-1",
            "department_code": "missing",
        },
    )

    with pytest.raises(ValidationError) as error:
        sync_employee_from_hr(employee, hr_client=hr_client)

    assert "department_code" in error.value.message_dict
