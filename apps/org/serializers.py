from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers

from apps.employees.models import Employee
from apps.employees.permissions import can_view_private_employee_fields
from apps.org.models import Department


class DepartmentBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = (
            "code",
            "name",
        )


class DepartmentListSerializer(serializers.ModelSerializer):
    parent = DepartmentBriefSerializer(read_only=True)
    employee_count = serializers.IntegerField(
        source="active_employee_count",
        read_only=True,
    )

    class Meta:
        model = Department
        fields = (
            "code",
            "name",
            "parent",
            "employee_count",
        )


class DepartmentStructureNodeSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    employee_count = serializers.IntegerField()
    children = serializers.SerializerMethodField()

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_children(self, node: dict) -> list[dict]:
        return DepartmentStructureNodeSerializer(
            node["children"],
            many=True,
        ).data


class OrgEmployeeQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        allow_blank=True,
        max_length=100,
        required=False,
        trim_whitespace=True,
    )
    department = serializers.CharField(
        allow_blank=True,
        max_length=64,
        required=False,
        trim_whitespace=True,
    )


class EmployeePrivacyMixin:
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
        return employee.is_phone_visible or can_view_private_employee_fields(
            self.context.get("viewer_employee"),
            employee,
        )

    def _can_view_birthdate(self, employee: Employee) -> bool:
        return employee.is_birthdate_visible or can_view_private_employee_fields(
            self.context.get("viewer_employee"),
            employee,
        )


class OrgEmployeeReferenceSerializer(
    EmployeePrivacyMixin,
    serializers.ModelSerializer,
):
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


class OrgEmployeeListSerializer(OrgEmployeeReferenceSerializer):
    manager = OrgEmployeeReferenceSerializer(read_only=True)
    hrbp = OrgEmployeeReferenceSerializer(read_only=True)
    current_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = OrgEmployeeReferenceSerializer.Meta.fields + (
            "manager",
            "hrbp",
            "city",
            "current_photo_url",
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_current_photo_url(self, employee: Employee) -> str | None:
        if not employee.current_photo:
            return None

        request = self.context.get("request")
        url = employee.current_photo.url

        if request is None:
            return url

        return request.build_absolute_uri(url)
