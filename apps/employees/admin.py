from django.contrib import admin

from apps.employees.models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "email",
        "login",
        "department",
        "manager",
        "is_active",
    )
    list_filter = ("is_active", "department")
    search_fields = (
        "first_name",
        "last_name",
        "middle_name",
        "email",
        "login",
        "external_id",
    )
    readonly_fields = ("employee_uuid", "created_at", "updated_at")
