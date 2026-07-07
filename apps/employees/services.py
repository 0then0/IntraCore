from collections.abc import Mapping

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.employees.models import Employee

PERSONAL_PROFILE_UPDATE_FIELDS = {
    "first_name",
    "last_name",
    "middle_name",
    "phone",
    "is_phone_visible",
    "birthdate",
    "is_birthdate_visible",
    "telegram_username",
    "city",
    "about",
    "hobbies",
    "education",
}

ADMIN_EMPLOYEE_UPDATE_FIELDS = PERSONAL_PROFILE_UPDATE_FIELDS | {
    "department",
    "email",
    "external_id",
    "hired_at",
    "hrbp",
    "is_active",
    "login",
    "manager",
    "position",
}

ALLOWED_PHOTO_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}
MAX_PHOTO_SIZE_BYTES = 5 * 1024 * 1024


@transaction.atomic
def update_own_profile(employee: Employee, data: Mapping) -> Employee:
    return _update_employee(employee, data, PERSONAL_PROFILE_UPDATE_FIELDS)


@transaction.atomic
def update_employee_as_admin(employee: Employee, data: Mapping) -> Employee:
    return _update_employee(employee, data, ADMIN_EMPLOYEE_UPDATE_FIELDS)


@transaction.atomic
def upload_pending_photo(employee: Employee, photo) -> Employee:
    employee = Employee.objects.select_for_update().get(pk=employee.pk)

    if employee.pending_photo:
        raise ValidationError(
            {"photo": "A photo is already pending moderation."},
        )

    employee.pending_photo = photo
    employee.pending_photo_uploaded_at = timezone.now()
    employee.photo_rejection_reason = ""
    employee.photo_moderated_at = None
    employee.photo_rejection_email_sent_at = None
    employee.save(
        update_fields=[
            "pending_photo",
            "pending_photo_uploaded_at",
            "photo_rejection_reason",
            "photo_moderated_at",
            "photo_rejection_email_sent_at",
            "updated_at",
        ],
    )

    return employee


@transaction.atomic
def approve_pending_photo(employee: Employee) -> Employee:
    employee = Employee.objects.select_for_update().get(pk=employee.pk)

    if not employee.pending_photo:
        return employee

    employee.current_photo = employee.pending_photo
    employee.pending_photo = ""
    employee.pending_photo_uploaded_at = None
    employee.photo_rejection_reason = ""
    employee.photo_moderated_at = timezone.now()
    employee.photo_rejection_email_sent_at = None
    employee.save(
        update_fields=[
            "current_photo",
            "pending_photo",
            "pending_photo_uploaded_at",
            "photo_rejection_reason",
            "photo_moderated_at",
            "photo_rejection_email_sent_at",
            "updated_at",
        ],
    )

    return employee


@transaction.atomic
def reject_pending_photo(employee: Employee, *, reason: str) -> Employee:
    reason = reason.strip()

    if not reason:
        raise ValidationError({"reason": "Rejection reason is required."})

    employee = Employee.objects.select_for_update().get(pk=employee.pk)

    if not employee.pending_photo:
        return employee

    employee.pending_photo = ""
    employee.pending_photo_uploaded_at = None
    employee.photo_rejection_reason = reason
    employee.photo_moderated_at = timezone.now()
    employee.photo_rejection_email_sent_at = None
    employee.save(
        update_fields=[
            "pending_photo",
            "pending_photo_uploaded_at",
            "photo_rejection_reason",
            "photo_moderated_at",
            "photo_rejection_email_sent_at",
            "updated_at",
        ],
    )

    from apps.employees.tasks import send_photo_rejection_email

    transaction.on_commit(lambda: send_photo_rejection_email.delay(employee.pk))

    return employee


def _update_employee(
    employee: Employee,
    data: Mapping,
    allowed_fields: set[str],
) -> Employee:
    unexpected_fields = set(data) - allowed_fields

    if unexpected_fields:
        raise ValidationError(
            {field: "This field cannot be updated." for field in unexpected_fields},
        )

    for field, value in data.items():
        setattr(employee, field, value)

    if not data:
        return employee

    employee.full_clean()

    update_fields = list(data)
    update_fields.append("updated_at")

    try:
        employee.save(update_fields=update_fields)
    except IntegrityError as error:
        raise ValidationError(
            {
                "non_field_errors": [
                    "Employee update violates database constraints.",
                ],
            },
        ) from error

    return employee
