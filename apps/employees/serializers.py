from collections.abc import Mapping

from django.urls import reverse
from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers

from apps.employees.models import Employee
from apps.employees.permissions import can_view_private_employee_fields
from apps.employees.services import ALLOWED_PHOTO_CONTENT_TYPES, MAX_PHOTO_SIZE_BYTES
from apps.org.models import Department
from apps.org.serializers import DepartmentBriefSerializer


class RejectUnknownFieldsMixin:
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown_fields = set(data) - set(self.fields)
            if unknown_fields:
                raise serializers.ValidationError(
                    {
                        field: ["This field cannot be updated."]
                        for field in sorted(unknown_fields)
                    },
                )

        return super().to_internal_value(data)


class EmployeeNestedSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="employee_uuid", read_only=True)
    full_name = serializers.CharField(read_only=True)
    department = DepartmentBriefSerializer(read_only=True)
    phone = serializers.SerializerMethodField()
    birthdate = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = (
            "id",
            "email",
            "login",
            "full_name",
            "first_name",
            "last_name",
            "middle_name",
            "position",
            "department",
            "phone",
            "is_phone_visible",
            "birthdate",
            "is_birthdate_visible",
        )

    @extend_schema_field(OpenApiTypes.STR)
    def get_phone(self, employee: Employee) -> str | None:
        if self._can_view_phone(employee):
            return employee.phone

        return None

    @extend_schema_field(OpenApiTypes.DATE)
    def get_birthdate(self, employee: Employee):
        if self._can_view_birthdate(employee):
            return employee.birthdate

        return None

    def _can_view_phone(self, employee: Employee) -> bool:
        if self.context.get("can_view_all_employee_fields"):
            return True

        return employee.is_phone_visible or can_view_private_employee_fields(
            self.context.get("viewer_employee"),
            employee,
        )

    def _can_view_birthdate(self, employee: Employee) -> bool:
        if self.context.get("can_view_all_employee_fields"):
            return True

        return employee.is_birthdate_visible or can_view_private_employee_fields(
            self.context.get("viewer_employee"),
            employee,
        )


class EmployeeDetailSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="employee_uuid", read_only=True)
    external_id = serializers.SerializerMethodField()
    full_name = serializers.CharField(read_only=True)
    department = DepartmentBriefSerializer(read_only=True)
    manager = EmployeeNestedSerializer(read_only=True)
    hrbp = EmployeeNestedSerializer(read_only=True)
    phone = serializers.SerializerMethodField()
    birthdate = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    current_photo_url = serializers.SerializerMethodField()
    has_pending_photo = serializers.SerializerMethodField()
    pending_photo_uploaded_at = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = (
            "id",
            "external_id",
            "email",
            "login",
            "full_name",
            "first_name",
            "last_name",
            "middle_name",
            "position",
            "department",
            "manager",
            "hrbp",
            "phone",
            "is_phone_visible",
            "birthdate",
            "is_birthdate_visible",
            "telegram_username",
            "city",
            "about",
            "hobbies",
            "education",
            "current_photo_url",
            "has_pending_photo",
            "pending_photo_uploaded_at",
            "hired_at",
            "is_active",
            "created_at",
            "updated_at",
        )

    @extend_schema_field(OpenApiTypes.STR)
    def get_external_id(self, employee: Employee) -> str | None:
        if self._can_view_private(employee):
            return employee.external_id

        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_phone(self, employee: Employee) -> str | None:
        if employee.is_phone_visible or self._can_view_private(employee):
            return employee.phone

        return None

    @extend_schema_field(OpenApiTypes.DATE)
    def get_birthdate(self, employee: Employee):
        if employee.is_birthdate_visible or self._can_view_private(employee):
            return employee.birthdate

        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_city(self, employee: Employee) -> str:
        return employee.effective_city

    @extend_schema_field(OpenApiTypes.URI)
    def get_current_photo_url(self, employee: Employee) -> str | None:
        if not employee.current_photo:
            return None

        request = self.context.get("request")
        url = employee.current_photo.url

        if request is None:
            return url

        return request.build_absolute_uri(url)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_has_pending_photo(self, employee: Employee) -> bool:
        if not self._can_view_private(employee):
            return False

        return employee.has_pending_photo

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_pending_photo_uploaded_at(self, employee: Employee):
        if not self._can_view_private(employee):
            return None

        return employee.pending_photo_uploaded_at

    def _can_view_private(self, employee: Employee) -> bool:
        if self.context.get("can_view_all_employee_fields"):
            return True

        return can_view_private_employee_fields(
            self.context.get("viewer_employee"),
            employee,
        )


class ProfilePhotoUploadSerializer(serializers.Serializer):
    photo = serializers.ImageField()
    captcha_token = serializers.CharField(
        allow_blank=False,
        max_length=4096,
        required=False,
        write_only=True,
    )

    def validate_photo(self, photo):
        if photo.size > MAX_PHOTO_SIZE_BYTES:
            raise serializers.ValidationError("Photo size must not exceed 5 MB.")

        content_type = getattr(photo, "content_type", "")
        if content_type not in ALLOWED_PHOTO_CONTENT_TYPES:
            raise serializers.ValidationError(
                "Photo must be a JPEG, PNG, or WebP image.",
            )

        return photo


class PhotoRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(
        allow_blank=False,
        max_length=500,
        trim_whitespace=True,
    )


class HrSyncQueuedSerializer(serializers.Serializer):
    status = serializers.CharField()
    employee_id = serializers.UUIDField()


class PhotoModerationItemSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="employee_uuid", read_only=True)
    full_name = serializers.CharField(read_only=True)
    current_photo_url = serializers.SerializerMethodField()
    pending_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = (
            "id",
            "email",
            "login",
            "full_name",
            "current_photo_url",
            "pending_photo_url",
            "pending_photo_uploaded_at",
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_current_photo_url(self, employee: Employee) -> str | None:
        return _build_file_url(self.context.get("request"), employee.current_photo)

    @extend_schema_field(OpenApiTypes.URI)
    def get_pending_photo_url(self, employee: Employee) -> str | None:
        if not employee.pending_photo:
            return None

        url = reverse(
            "admin-photo-moderation-pending-photo",
            kwargs={"employee_id": employee.employee_uuid},
        )
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url


def _build_file_url(request, file_field) -> str | None:
    if not file_field:
        return None

    url = file_field.url

    if request is None:
        return url

    return request.build_absolute_uri(url)


class EmployeeProfileUpdateSerializer(
    RejectUnknownFieldsMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model = Employee
        fields = (
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
        )

    def validate_birthdate(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError("Birthdate cannot be in the future.")

        return value


class AdminEmployeeUpdateSerializer(
    RejectUnknownFieldsMixin,
    serializers.ModelSerializer,
):
    department = serializers.SlugRelatedField(
        allow_null=True,
        slug_field="code",
        queryset=Department.objects.all(),
        required=False,
    )
    manager = serializers.SlugRelatedField(
        allow_null=True,
        slug_field="employee_uuid",
        queryset=Employee.objects.all(),
        required=False,
    )
    hrbp = serializers.SlugRelatedField(
        allow_null=True,
        slug_field="employee_uuid",
        queryset=Employee.objects.all(),
        required=False,
    )

    class Meta:
        model = Employee
        fields = (
            "external_id",
            "email",
            "login",
            "first_name",
            "last_name",
            "middle_name",
            "position",
            "department",
            "manager",
            "hrbp",
            "phone",
            "is_phone_visible",
            "birthdate",
            "is_birthdate_visible",
            "telegram_username",
            "city",
            "about",
            "hobbies",
            "education",
            "hired_at",
            "is_active",
        )

    def validate_birthdate(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError("Birthdate cannot be in the future.")

        return value

    def validate(self, attrs):
        employee = self.instance

        if employee is None:
            return attrs

        manager = attrs.get("manager")
        hrbp = attrs.get("hrbp")

        if manager is not None and manager.pk == employee.pk:
            raise serializers.ValidationError(
                {"manager": ["Employee cannot be their own manager."]},
            )

        if hrbp is not None and hrbp.pk == employee.pk:
            raise serializers.ValidationError(
                {"hrbp": ["Employee cannot be their own HRBP."]},
            )

        return attrs
