from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.permissions import BasePermission

if TYPE_CHECKING:
    from apps.employees.models import Employee


def can_view_private_employee_fields(
    viewer_employee: Employee | None,
    target_employee: Employee,
) -> bool:
    return bool(viewer_employee and viewer_employee.pk == target_employee.pk)


class IsStaffUser(BasePermission):
    message = "Admin access is required."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_staff)
