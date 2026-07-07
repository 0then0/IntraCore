from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)
from rest_framework import status
from rest_framework.exceptions import ValidationError as DrfValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.feature_flags import hr_sync_enabled
from apps.employees.permissions import IsStaffUser
from apps.employees.selectors import (
    get_employee_by_uuid,
    get_employee_for_user,
    get_optional_employee_for_user,
    pending_photo_moderation_queryset,
)
from apps.employees.serializers import (
    AdminEmployeeUpdateSerializer,
    EmployeeDetailSerializer,
    EmployeeProfileUpdateSerializer,
    HrSyncQueuedSerializer,
    PhotoModerationItemSerializer,
    PhotoRejectSerializer,
    ProfilePhotoUploadSerializer,
)
from apps.employees.services import (
    approve_pending_photo,
    reject_pending_photo,
    update_employee_as_admin,
    update_own_profile,
    upload_pending_photo,
)

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


class ProfilePhotoUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Profile"],
        request=ProfilePhotoUploadSerializer,
        responses={
            200: EmployeeDetailSerializer,
            400: OpenApiResponse(description="Photo upload validation failed."),
            401: OpenApiResponse(description="Authentication is required."),
            404: OpenApiResponse(description="Employee profile was not found."),
        },
    )
    def post(self, request):
        employee = get_employee_for_user(request.user)
        serializer = ProfilePhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            employee = upload_pending_photo(
                employee, serializer.validated_data["photo"]
            )
        except DjangoValidationError as error:
            _raise_drf_validation_error(error)

        response_serializer = EmployeeDetailSerializer(
            employee,
            context=_serializer_context(request),
        )

        return Response(response_serializer.data)


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


class AdminEmployeeHrSyncView(APIView):
    permission_classes = [IsAuthenticated, IsStaffUser]

    @extend_schema(
        tags=["Admin Employees"],
        parameters=[EMPLOYEE_ID_PARAMETER],
        request=None,
        responses={
            202: HrSyncQueuedSerializer,
            400: OpenApiResponse(description="Employee has no external HR id."),
            401: OpenApiResponse(description="Authentication is required."),
            403: OpenApiResponse(description="Admin access is required."),
            404: OpenApiResponse(description="Employee was not found."),
            503: OpenApiResponse(description="HR sync is disabled."),
        },
    )
    def post(self, request, id):
        employee = get_employee_by_uuid(id)

        if not hr_sync_enabled():
            return Response(
                {
                    "code": "hr_sync_disabled",
                    "detail": "HR sync is disabled.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not employee.external_id:
            return Response(
                {
                    "code": "employee_external_id_missing",
                    "detail": "Employee has no external HR id.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.employees.tasks import sync_employee_from_hr_task

        transaction.on_commit(lambda: sync_employee_from_hr_task.delay(employee.pk))

        return Response(
            {
                "status": "queued",
                "employee_id": employee.employee_uuid,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class AdminPhotoModerationListView(ListAPIView):
    permission_classes = [IsAuthenticated, IsStaffUser]
    serializer_class = PhotoModerationItemSerializer

    @extend_schema(
        tags=["Photo Moderation"],
        responses={
            200: PhotoModerationItemSerializer(many=True),
            401: OpenApiResponse(description="Authentication is required."),
            403: OpenApiResponse(description="Admin access is required."),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return pending_photo_moderation_queryset().order_by(
            "-pending_photo_uploaded_at",
            "last_name",
            "first_name",
        )


class AdminPhotoModerationApproveView(APIView):
    permission_classes = [IsAuthenticated, IsStaffUser]

    @extend_schema(
        tags=["Photo Moderation"],
        parameters=[EMPLOYEE_ID_PARAMETER],
        request=None,
        responses={
            200: EmployeeDetailSerializer,
            401: OpenApiResponse(description="Authentication is required."),
            403: OpenApiResponse(description="Admin access is required."),
            404: OpenApiResponse(description="Employee was not found."),
        },
    )
    def post(self, request, employee_id):
        employee = get_employee_by_uuid(employee_id)
        employee = approve_pending_photo(employee)
        serializer = EmployeeDetailSerializer(
            employee,
            context=_admin_serializer_context(request),
        )

        return Response(serializer.data)


class AdminPhotoModerationRejectView(APIView):
    permission_classes = [IsAuthenticated, IsStaffUser]

    @extend_schema(
        tags=["Photo Moderation"],
        parameters=[EMPLOYEE_ID_PARAMETER],
        request=PhotoRejectSerializer,
        responses={
            200: EmployeeDetailSerializer,
            400: OpenApiResponse(description="Reject reason validation failed."),
            401: OpenApiResponse(description="Authentication is required."),
            403: OpenApiResponse(description="Admin access is required."),
            404: OpenApiResponse(description="Employee was not found."),
        },
    )
    def post(self, request, employee_id):
        employee = get_employee_by_uuid(employee_id)
        serializer = PhotoRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            employee = reject_pending_photo(
                employee,
                reason=serializer.validated_data["reason"],
            )
        except DjangoValidationError as error:
            _raise_drf_validation_error(error)

        response_serializer = EmployeeDetailSerializer(
            employee,
            context=_admin_serializer_context(request),
        )

        return Response(response_serializer.data)
