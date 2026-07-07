from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils import timezone

from apps.common.feature_flags import photo_moderation_email_enabled
from apps.employees.models import Employee
from apps.employees.services import sync_employee_from_hr
from apps.integrations.exceptions import (
    HrEmployeeLockedError,
    HrSyncDisabledError,
    HrTimeoutError,
    HrUpstreamError,
    HrValidationError,
)
from celery import shared_task


@shared_task
def send_photo_rejection_email(employee_id: int) -> None:
    if not photo_moderation_email_enabled():
        return

    try:
        employee = Employee.objects.get(pk=employee_id)
    except Employee.DoesNotExist:
        return

    if not employee.photo_rejection_reason:
        return

    if employee.photo_rejection_email_sent_at:
        return

    send_mail(
        subject="Profile photo rejected",
        message=(
            "Your profile photo was rejected.\n\n"
            f"Reason: {employee.photo_rejection_reason}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[employee.email],
        fail_silently=False,
    )

    employee.photo_rejection_email_sent_at = timezone.now()
    employee.save(update_fields=["photo_rejection_email_sent_at", "updated_at"])


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
