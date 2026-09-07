from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.employees.models import Employee, PhotoRejectionNotification
from apps.employees.tasks import (
    PhotoRejectionDeliveryError,
    send_photo_rejection_email,
    send_photo_rejection_notification_email,
)

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
        hired_at=date(2020, 1, 10),
    )


def create_notification(employee: Employee) -> PhotoRejectionNotification:
    return PhotoRejectionNotification.objects.create(
        employee=employee,
        recipient_email=employee.email,
        reason="Low image quality.",
    )


def test_rejection_email_task_does_not_send_when_flag_disabled(
    django_user_model,
    settings,
    mocker,
):
    settings.PHOTO_MODERATION_EMAIL_ENABLED = False
    notification = create_notification(create_employee(django_user_model))
    send_mail = mocker.patch("apps.employees.tasks.send_mail")

    send_photo_rejection_notification_email(notification.pk)

    send_mail.assert_not_called()
    notification.refresh_from_db()
    assert notification.sent_at is None


def test_rejection_email_task_sends_once_when_enabled(
    django_user_model,
    settings,
    mocker,
):
    settings.PHOTO_MODERATION_EMAIL_ENABLED = True
    notification = create_notification(create_employee(django_user_model))
    send_mail = mocker.patch("apps.employees.tasks.send_mail", return_value=1)

    send_photo_rejection_notification_email(notification.pk)
    send_photo_rejection_notification_email(notification.pk)

    send_mail.assert_called_once()
    notification.refresh_from_db()
    assert notification.sent_at is not None


def test_rejection_email_uses_immutable_notification_data(
    django_user_model,
    settings,
    mocker,
):
    settings.PHOTO_MODERATION_EMAIL_ENABLED = True
    employee = create_employee(django_user_model)
    notification = create_notification(employee)
    employee.email = "changed@example.com"
    employee.photo_rejection_reason = ""
    employee.save(update_fields=["email", "photo_rejection_reason"])
    send_mail = mocker.patch("apps.employees.tasks.send_mail", return_value=1)

    send_photo_rejection_notification_email(notification.pk)

    assert send_mail.call_args.kwargs["recipient_list"] == ["employee@example.com"]
    assert "Low image quality." in send_mail.call_args.kwargs["message"]


def test_rejection_email_reclaims_stale_delivery_claim(
    django_user_model,
    settings,
    mocker,
):
    settings.PHOTO_MODERATION_EMAIL_ENABLED = True
    settings.PHOTO_REJECTION_EMAIL_CLAIM_TIMEOUT_SECONDS = 60
    notification = create_notification(create_employee(django_user_model))
    notification.delivery_claimed_at = timezone.now() - timedelta(seconds=61)
    notification.save(update_fields=["delivery_claimed_at"])
    send_mail = mocker.patch("apps.employees.tasks.send_mail", return_value=1)

    send_photo_rejection_notification_email(notification.pk)

    send_mail.assert_called_once()
    notification.refresh_from_db()
    assert notification.sent_at is not None


def test_rejection_email_releases_claim_after_delivery_error(
    django_user_model,
    settings,
    mocker,
):
    settings.PHOTO_MODERATION_EMAIL_ENABLED = True
    notification = create_notification(create_employee(django_user_model))
    mocker.patch("apps.employees.tasks.send_mail", side_effect=RuntimeError)

    with pytest.raises(PhotoRejectionDeliveryError):
        send_photo_rejection_notification_email.run(notification.pk)

    notification.refresh_from_db()
    assert notification.delivery_claimed_at is None
    assert notification.sent_at is None


def test_rejection_email_does_not_reclaim_recent_delivery_claim(
    django_user_model,
    settings,
    mocker,
):
    settings.PHOTO_MODERATION_EMAIL_ENABLED = True
    notification = create_notification(create_employee(django_user_model))
    notification.delivery_claimed_at = timezone.now()
    notification.save(update_fields=["delivery_claimed_at"])
    send_mail = mocker.patch("apps.employees.tasks.send_mail", return_value=1)

    send_photo_rejection_notification_email(notification.pk)

    send_mail.assert_not_called()


def test_legacy_rejection_email_task_keeps_employee_id_contract(
    django_user_model,
    settings,
    mocker,
):
    settings.PHOTO_MODERATION_EMAIL_ENABLED = True
    employee = create_employee(django_user_model)
    employee.photo_rejection_reason = "Legacy rejection reason."
    employee.save(update_fields=["photo_rejection_reason", "updated_at"])
    send_mail = mocker.patch("apps.employees.tasks.send_mail", return_value=1)

    send_photo_rejection_email(employee.pk)

    assert send_mail.call_args.kwargs["recipient_list"] == [employee.email]
    assert "Legacy rejection reason." in send_mail.call_args.kwargs["message"]
    employee.refresh_from_db()
    assert employee.photo_rejection_email_sent_at is not None
