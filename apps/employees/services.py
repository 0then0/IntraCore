from collections.abc import Mapping
from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.feature_flags import hr_sync_enabled
from apps.employees.models import Employee
from apps.integrations.exceptions import HrSyncDisabledError
from apps.integrations.hr_client import HrClient
from apps.org.models import Department

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

HR_SYNC_TEXT_FIELDS = {
    "email",
    "login",
    "first_name",
    "last_name",
    "middle_name",
    "position",
    "phone",
    "telegram_username",
    "city",
    "add_location",
    "location_city",
    "location",
}
HR_SYNC_FIELDS = HR_SYNC_TEXT_FIELDS | {
    "department",
    "hired_at",
    "is_active",
}


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


def sync_employee_from_hr(
    employee: Employee,
    *,
    hr_client: HrClient | None = None,
) -> Employee:
    if not hr_sync_enabled():
        raise HrSyncDisabledError()

    if not employee.external_id:
        raise ValidationError({"external_id": "Employee has no external HR id."})

    client = hr_client or HrClient()
    payload = client.get_employee(employee.external_id)
    data = _employee_data_from_hr_payload(employee, payload)

    return _sync_employee_data(employee, data)


@transaction.atomic
def _sync_employee_data(employee: Employee, data: Mapping) -> Employee:
    employee = Employee.objects.select_for_update().get(pk=employee.pk)

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
                    "HR sync violates employee database constraints.",
                ],
            },
        ) from error

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


def _employee_data_from_hr_payload(employee: Employee, payload: Mapping) -> dict:
    payload_external_id = payload.get("external_id")
    if payload_external_id != employee.external_id:
        raise ValidationError(
            {"external_id": "HR response external id does not match employee."},
        )

    data = {}

    for field in HR_SYNC_TEXT_FIELDS:
        if field in payload:
            data[field] = payload[field] or ""

    if "is_active" in payload:
        if not isinstance(payload["is_active"], bool):
            raise ValidationError({"is_active": "HR is_active must be boolean."})
        data["is_active"] = payload["is_active"]

    if "hired_at" in payload:
        data["hired_at"] = _parse_hr_date(payload["hired_at"], field_name="hired_at")

    if "department_code" in payload:
        data["department"] = _department_from_hr_code(payload["department_code"])

    return {field: value for field, value in data.items() if field in HR_SYNC_FIELDS}


def _parse_hr_date(value, *, field_name: str) -> date | None:
    if value in (None, ""):
        return None

    if not isinstance(value, str):
        raise ValidationError({field_name: "HR date value must be an ISO date string."})

    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValidationError(
            {field_name: "HR date value must be a valid ISO date."},
        ) from error


def _department_from_hr_code(code: str | None) -> Department | None:
    if not code:
        return None

    try:
        return Department.objects.get(code=code)
    except Department.DoesNotExist as error:
        raise ValidationError(
            {"department_code": "HR department code was not found."},
        ) from error
