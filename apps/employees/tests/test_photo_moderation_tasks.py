from datetime import date

import pytest

from apps.employees.models import Employee
from apps.employees.tasks import send_photo_rejection_email

pytestmark = pytest.mark.django_db


def create_employee(django_user_model) -> Employee:
    user = django_user_model.objects.create_user(
        username="employee",
        email="employee@example.com",
        password="password",
    )

    return Employee.objects.create(
        user=user,
        email="employee@example.com",
        login="employee",
        first_name="First",
        last_name="Last",
        photo_rejection_reason="Low image quality.",
        hired_at=date(2020, 1, 10),
    )


def test_rejection_email_task_does_not_send_when_flag_disabled(
    django_user_model,
    settings,
    mocker,
):
    settings.PHOTO_MODERATION_EMAIL_ENABLED = False
    employee = create_employee(django_user_model)
    send_mail = mocker.patch("apps.employees.tasks.send_mail")

    send_photo_rejection_email(employee.pk)

    send_mail.assert_not_called()
    employee.refresh_from_db()
    assert employee.photo_rejection_email_sent_at is None


def test_rejection_email_task_sends_once_when_enabled(
    django_user_model,
    settings,
    mocker,
):
    settings.PHOTO_MODERATION_EMAIL_ENABLED = True
    employee = create_employee(django_user_model)
    send_mail = mocker.patch("apps.employees.tasks.send_mail")

    send_photo_rejection_email(employee.pk)
    send_photo_rejection_email(employee.pk)

    send_mail.assert_called_once()
    employee.refresh_from_db()
    assert employee.photo_rejection_email_sent_at is not None
