from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.employees.models import Employee
from apps.employees.services import upload_pending_photo

pytestmark = pytest.mark.django_db


def create_employee(django_user_model, *, pending_photo: str = "") -> Employee:
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
        pending_photo=pending_photo,
        hired_at=date(2020, 1, 10),
    )


def test_disabled_captcha_does_not_call_client(django_user_model, settings, mocker):
    settings.CAPTCHA_ENABLED = False
    employee = create_employee(django_user_model, pending_photo="already-pending.png")
    captcha_client = mocker.Mock()

    with pytest.raises(ValidationError):
        upload_pending_photo(
            employee,
            mocker.Mock(),
            captcha_token="token-value",
            captcha_client=captcha_client,
        )

    captcha_client.verify.assert_not_called()


def test_enabled_captcha_calls_client_before_photo_state_change(
    django_user_model,
    settings,
    mocker,
):
    settings.CAPTCHA_ENABLED = True
    employee = create_employee(django_user_model, pending_photo="already-pending.png")
    captcha_client = mocker.Mock()

    with pytest.raises(ValidationError):
        upload_pending_photo(
            employee,
            mocker.Mock(),
            captcha_token="token-value",
            captcha_client=captcha_client,
        )

    captcha_client.verify.assert_called_once_with("token-value")


def test_enabled_captcha_requires_token(django_user_model, settings, mocker):
    settings.CAPTCHA_ENABLED = True
    employee = create_employee(django_user_model)
    captcha_client = mocker.Mock()

    with pytest.raises(ValidationError) as error:
        upload_pending_photo(employee, mocker.Mock(), captcha_client=captcha_client)

    assert "captcha_token" in error.value.message_dict
    captcha_client.verify.assert_not_called()
