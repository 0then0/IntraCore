from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.employees.models import Employee


def employee_detail_queryset():
    return Employee.objects.select_related(
        "department",
        "manager",
        "manager__department",
        "hrbp",
        "hrbp__department",
    )


def pending_photo_moderation_queryset():
    return employee_detail_queryset().exclude(pending_photo="")


def get_employee_by_uuid(employee_uuid) -> Employee:
    return get_object_or_404(employee_detail_queryset(), employee_uuid=employee_uuid)


def get_employee_for_user(user) -> Employee:
    if not user.is_authenticated:
        raise Http404

    return get_object_or_404(employee_detail_queryset(), user=user)


def get_optional_employee_for_user(user) -> Employee | None:
    if not user.is_authenticated:
        return None

    try:
        return employee_detail_queryset().get(user=user)
    except Employee.DoesNotExist:
        return None
