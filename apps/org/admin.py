from django.contrib import admin

from apps.org.models import Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "parent")
    list_filter = ("parent",)
    search_fields = ("name", "code")
