from collections.abc import Mapping

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

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


@transaction.atomic
def update_own_profile(employee: Employee, data: Mapping) -> Employee:
    return _update_employee(employee, data, PERSONAL_PROFILE_UPDATE_FIELDS)


@transaction.atomic
def update_employee_as_admin(employee: Employee, data: Mapping) -> Employee:
    return _update_employee(employee, data, ADMIN_EMPLOYEE_UPDATE_FIELDS)


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
