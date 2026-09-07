import logging
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

logger = logging.getLogger(__name__)


class PhotoRejectionDeliveryError(Exception):
    """Signals a retryable email delivery failure after releasing the claim."""


class PhotoPromotionError(Exception):
    """Signals a retryable failure while publishing an approved private photo."""


@shared_task(
    autoretry_for=(PhotoRejectionDeliveryError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
    task_reject_on_worker_lost=True,
)
def send_photo_rejection_email(employee_id: int) -> None:
    """Deliver legacy queue messages created before notification records existed."""
    if not photo_moderation_email_enabled():
        return

    try:
        employee = Employee.objects.get(pk=employee_id)
    except Employee.DoesNotExist:
        return

    if not employee.photo_rejection_reason or employee.photo_rejection_email_sent_at:
        return

    try:
        sent_count = send_mail(
            subject="Profile photo rejected",
            message=(
                "Your profile photo was rejected.\n\n"
                f"Reason: {employee.photo_rejection_reason}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[employee.email],
            fail_silently=False,
        )
        if sent_count != 1:
            raise RuntimeError("Photo rejection email was not accepted for delivery.")
    except Exception as error:
        logger.error(
            "Legacy photo rejection notification delivery failed.",
            extra={
                "employee_id": employee_id,
                "error_type": type(error).__name__,
                "event": "photo_rejection_notification_failed",
            },
        )
        raise PhotoRejectionDeliveryError() from None

    Employee.objects.filter(
        pk=employee.pk,
        photo_rejection_email_sent_at__isnull=True,
    ).update(photo_rejection_email_sent_at=timezone.now())


@shared_task(
    autoretry_for=(PhotoRejectionDeliveryError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
    task_reject_on_worker_lost=True,
)
def send_photo_rejection_notification_email(notification_id: int) -> None:
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
    except Exception as error:
        _release_photo_rejection_notification(notification_id)
        logger.error(
            "Photo rejection notification delivery failed.",
            extra={
                "event": "photo_rejection_notification_failed",
                "error_type": type(error).__name__,
            },
        )
        raise PhotoRejectionDeliveryError() from None

    _mark_photo_rejection_notification_sent(notification_id)


@shared_task(
    autoretry_for=(PhotoPromotionError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_kwargs={"max_retries": 10},
    acks_late=True,
    task_reject_on_worker_lost=True,
)
def publish_approved_photo(employee_id: int) -> None:
    promotion = _claim_approved_photo_promotion(employee_id)
    if promotion is None:
        return

    approved_photo_name, destination_name = promotion
    try:
        if not default_storage.exists(destination_name):
            private_storage = PrivatePendingPhotoStorage()
            with private_storage.open(approved_photo_name, "rb") as source_file:
                saved_name = default_storage.save(destination_name, source_file)
            if saved_name != destination_name:
                default_storage.delete(saved_name)
                raise PhotoPromotionError("Approved photo destination already exists.")
    except FileNotFoundError as error:
        _release_approved_photo_promotion(employee_id, approved_photo_name)
        logger.warning(
            "Approved photo source file is unavailable.",
            extra={
                "employee_id": employee_id,
                "error_type": type(error).__name__,
                "event": "approved_photo_publication_failed",
            },
        )
        raise PhotoPromotionError("Approved photo file is unavailable.") from None
    except Exception as error:
        _release_approved_photo_promotion(employee_id, approved_photo_name)
        logger.error(
            "Approved photo publication failed.",
            extra={
                "employee_id": employee_id,
                "error_type": type(error).__name__,
                "event": "approved_photo_publication_failed",
            },
        )
        raise PhotoPromotionError() from None

    _finalize_approved_photo_promotion(
        employee_id,
        approved_photo_name,
        destination_name,
    )


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


@transaction.atomic
def _claim_approved_photo_promotion(employee_id: int) -> tuple[str, str] | None:
    try:
        employee = Employee.objects.select_for_update().get(pk=employee_id)
    except Employee.DoesNotExist:
        return None

    if not employee.approved_photo or not employee.approved_photo_public_name:
        return None

    claim_expired_at = timezone.now() - timedelta(
        seconds=settings.PHOTO_APPROVAL_PUBLISH_CLAIM_TIMEOUT_SECONDS,
    )
    if (
        employee.approved_photo_promotion_claimed_at
        and employee.approved_photo_promotion_claimed_at > claim_expired_at
    ):
        raise PhotoPromotionError("Approved photo promotion is already in progress.")

    employee.approved_photo_promotion_claimed_at = timezone.now()
    employee.save(update_fields=["approved_photo_promotion_claimed_at", "updated_at"])
    return employee.approved_photo.name, employee.approved_photo_public_name


@transaction.atomic
def _release_approved_photo_promotion(
    employee_id: int,
    approved_photo_name: str,
) -> None:
    Employee.objects.filter(
        pk=employee_id,
        approved_photo=approved_photo_name,
    ).update(approved_photo_promotion_claimed_at=None)


@transaction.atomic
def _finalize_approved_photo_promotion(
    employee_id: int,
    approved_photo_name: str,
    destination_name: str,
) -> None:
    try:
        employee = Employee.objects.select_for_update().get(pk=employee_id)
    except Employee.DoesNotExist:
        return

    if (
        employee.approved_photo.name != approved_photo_name
        or employee.approved_photo_public_name != destination_name
    ):
        return

    previous_current_photo_name = employee.current_photo.name
    employee.current_photo.name = destination_name
    employee.approved_photo = ""
    employee.approved_photo_public_name = ""
    employee.approved_photo_promotion_claimed_at = None
    employee.pending_photo_uploaded_at = None
    employee.photo_rejection_reason = ""
    employee.photo_moderated_at = timezone.now()
    employee.photo_rejection_email_sent_at = None
    employee.save(
        update_fields=[
            "current_photo",
            "approved_photo",
            "approved_photo_public_name",
            "approved_photo_promotion_claimed_at",
            "pending_photo_uploaded_at",
            "photo_rejection_reason",
            "photo_moderated_at",
            "photo_rejection_email_sent_at",
            "updated_at",
        ],
    )

    transaction.on_commit(
        lambda name=approved_photo_name: delete_pending_photo_file.delay(name),
    )
    if previous_current_photo_name and previous_current_photo_name != destination_name:
        transaction.on_commit(
            lambda name=previous_current_photo_name: delete_current_photo_file.delay(
                name
            ),
        )
