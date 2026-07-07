from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views.decorators.http import require_POST
from wagtail.admin.auth import require_admin_access

from apps.employees.selectors import (
    get_employee_by_uuid,
    pending_photo_moderation_queryset,
)
from apps.employees.services import approve_pending_photo, reject_pending_photo


@require_admin_access
def photo_moderation_index(request):
    employees = pending_photo_moderation_queryset().order_by(
        "-pending_photo_uploaded_at",
        "last_name",
        "first_name",
    )

    return TemplateResponse(
        request,
        "employees/wagtail/photo_moderation_index.html",
        {"employees": employees},
    )


@require_admin_access
@require_POST
def photo_moderation_approve(request, employee_id):
    employee = get_employee_by_uuid(employee_id)
    approve_pending_photo(employee)
    messages.success(request, "Photo approved.")

    return redirect("wagtail-photo-moderation-index")


@require_admin_access
@require_POST
def photo_moderation_reject(request, employee_id):
    employee = get_employee_by_uuid(employee_id)
    reason = request.POST.get("reason", "")

    try:
        reject_pending_photo(employee, reason=reason)
    except ValidationError:
        messages.error(request, "Rejection reason is required.")
        return redirect("wagtail-photo-moderation-index")

    messages.success(request, "Photo rejected.")

    return redirect("wagtail-photo-moderation-index")
