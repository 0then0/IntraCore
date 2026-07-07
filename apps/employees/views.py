from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)
from rest_framework.exceptions import ValidationError as DrfValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.employees.permissions import IsStaffUser
from apps.employees.selectors import (
    get_employee_by_uuid,
    get_employee_for_user,
    get_optional_employee_for_user,
)
from apps.employees.serializers import (
    AdminEmployeeUpdateSerializer,
    EmployeeDetailSerializer,
    EmployeeProfileUpdateSerializer,
)
from apps.employees.services import update_employee_as_admin, update_own_profile

EMPLOYEE_ID_PARAMETER = OpenApiParameter(
    name="id",
    type=OpenApiTypes.UUID,
    location=OpenApiParameter.PATH,
    description="Employee UUID.",
)


def _serializer_context(request) -> dict:
    return {
        "request": request,
        "viewer_employee": get_optional_employee_for_user(request.user),
    }


def _admin_serializer_context(request) -> dict:
    context = _serializer_context(request)
    context["can_view_all_employee_fields"] = True

    return context


def _raise_drf_validation_error(error: DjangoValidationError) -> None:
    if hasattr(error, "message_dict"):
        raise DrfValidationError(error.message_dict)

    raise DrfValidationError(error.messages)


class ProfileMeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Profile"],
        responses={
            200: EmployeeDetailSerializer,
            401: OpenApiResponse(description="Authentication is required."),
            404: OpenApiResponse(description="Employee profile was not found."),
        },
    )
    def get(self, request):
        employee = get_employee_for_user(request.user)
        serializer = EmployeeDetailSerializer(
            employee,
            context=_serializer_context(request),
        )

        return Response(serializer.data)

    @extend_schema(
        tags=["Profile"],
        request=EmployeeProfileUpdateSerializer,
        responses={
            200: EmployeeDetailSerializer,
            400: OpenApiResponse(description="Request body validation failed."),
            401: OpenApiResponse(description="Authentication is required."),
            404: OpenApiResponse(description="Employee profile was not found."),
        },
    )
    def patch(self, request):
        employee = get_employee_for_user(request.user)
        serializer = EmployeeProfileUpdateSerializer(
            employee,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        try:
            employee = update_own_profile(employee, serializer.validated_data)
        except DjangoValidationError as error:
            _raise_drf_validation_error(error)

        response_serializer = EmployeeDetailSerializer(
            employee,
            context=_serializer_context(request),
        )

        return Response(response_serializer.data)


class EmployeeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Employees"],
        parameters=[EMPLOYEE_ID_PARAMETER],
        responses={
            200: EmployeeDetailSerializer,
            401: OpenApiResponse(description="Authentication is required."),
            404: OpenApiResponse(description="Employee was not found."),
        },
    )
    def get(self, request, id):
        employee = get_employee_by_uuid(id)
        serializer = EmployeeDetailSerializer(
            employee,
            context=_serializer_context(request),
        )

        return Response(serializer.data)


class AdminEmployeeDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffUser]

    @extend_schema(
        tags=["Admin Employees"],
        parameters=[EMPLOYEE_ID_PARAMETER],
        request=AdminEmployeeUpdateSerializer,
        responses={
            200: EmployeeDetailSerializer,
            400: OpenApiResponse(description="Request body validation failed."),
            401: OpenApiResponse(description="Authentication is required."),
            403: OpenApiResponse(description="Admin access is required."),
            404: OpenApiResponse(description="Employee was not found."),
        },
    )
    def patch(self, request, id):
        employee = get_employee_by_uuid(id)
        serializer = AdminEmployeeUpdateSerializer(
            employee,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        try:
            employee = update_employee_as_admin(employee, serializer.validated_data)
        except DjangoValidationError as error:
            _raise_drf_validation_error(error)

        response_serializer = EmployeeDetailSerializer(
            employee,
            context=_admin_serializer_context(request),
        )

        return Response(response_serializer.data)
