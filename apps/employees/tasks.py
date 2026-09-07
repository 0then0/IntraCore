from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.common.feature_flags import photo_moderation_email_enabled
from apps.employees.models import Employee, PhotoRejectionNotification
from apps.employees.services import sync_employee_from_hr
from apps.employees.storage import PrivatePendingPhotoStorage
from apps.integrations.exceptions import (
    HrEmployeeLockedError,
    HrSyncDisabledError,
    HrTimeoutError,
    HrUpstreamError,
    HrValidationError,
)
from celery import shared_task


class PhotoRejectionDeliveryError(Exception):
    """Signals a retryable email delivery failure after releasing the claim."""


@shared_task(
    autoretry_for=(PhotoRejectionDeliveryError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
    task_reject_on_worker_lost=True,
)
def send_photo_rejection_email(notification_id: int) -> None:
    if not photo_moderation_email_enabled():
        return

    notification = _claim_photo_rejection_notification(notification_id)
    if notification is None:
        return

    try:
        sent_count = send_mail(
            subject="Profile photo rejected",
            message=(
                f"Your profile photo was rejected.\n\nReason: {notification.reason}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.recipient_email],
            fail_silently=False,
        )
        if sent_count != 1:
            raise RuntimeError("Photo rejection email was not accepted for delivery.")
    except Exception:
        _release_photo_rejection_notification(notification_id)
        raise PhotoRejectionDeliveryError() from None

    _mark_photo_rejection_notification_sent(notification_id)


@shared_task
def delete_pending_photo_file(name: str) -> None:
    PrivatePendingPhotoStorage().delete(name)


@shared_task
def delete_current_photo_file(name: str) -> None:
    default_storage.delete(name)


@shared_task(
    autoretry_for=(HrTimeoutError, HrUpstreamError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def sync_employee_from_hr_task(employee_id: int) -> str:
    try:
        employee = Employee.objects.get(pk=employee_id)
    except Employee.DoesNotExist:
        return "missing"

    try:
        sync_employee_from_hr(employee)
    except HrSyncDisabledError:
        return "disabled"
    except (ValidationError, HrValidationError, HrEmployeeLockedError):
        return "rejected"

    return "synced"


@transaction.atomic
def _claim_photo_rejection_notification(
    notification_id: int,
) -> PhotoRejectionNotification | None:
    try:
        notification = PhotoRejectionNotification.objects.select_for_update().get(
            pk=notification_id,
        )
    except PhotoRejectionNotification.DoesNotExist:
        return None

    claim_expired_at = timezone.now() - timedelta(
        seconds=settings.PHOTO_REJECTION_EMAIL_CLAIM_TIMEOUT_SECONDS,
    )
    if notification.sent_at or (
        notification.delivery_claimed_at
        and notification.delivery_claimed_at > claim_expired_at
    ):
        return None

    notification.delivery_claimed_at = timezone.now()
    notification.save(update_fields=["delivery_claimed_at"])
    return notification


@transaction.atomic
def _release_photo_rejection_notification(notification_id: int) -> None:
    PhotoRejectionNotification.objects.filter(
        pk=notification_id,
        sent_at__isnull=True,
    ).update(delivery_claimed_at=None)


@transaction.atomic
def _mark_photo_rejection_notification_sent(notification_id: int) -> None:
    PhotoRejectionNotification.objects.filter(
        pk=notification_id,
        sent_at__isnull=True,
    ).update(sent_at=timezone.now())
