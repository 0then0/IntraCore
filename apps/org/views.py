from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.employees.selectors import get_optional_employee_for_user
from apps.org.selectors import (
    department_list_queryset,
    filter_org_employees,
    get_department_structure,
    org_employee_queryset,
)
from apps.org.serializers import (
    DepartmentListSerializer,
    DepartmentStructureNodeSerializer,
    OrgEmployeeListSerializer,
    OrgEmployeeQuerySerializer,
)


class DepartmentListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DepartmentListSerializer

    @extend_schema(
        tags=["Org"],
        responses={
            200: DepartmentListSerializer(many=True),
            401: OpenApiResponse(description="Authentication is required."),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return department_list_queryset()


class DepartmentStructureView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Org"],
        responses={
            200: DepartmentStructureNodeSerializer(many=True),
            401: OpenApiResponse(description="Authentication is required."),
        },
    )
    def get(self, request):
        serializer = DepartmentStructureNodeSerializer(
            get_department_structure(),
            many=True,
        )

        return Response(serializer.data)


class OrgEmployeeListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrgEmployeeListSerializer

    @extend_schema(
        tags=["Org"],
        parameters=[
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Search by employee name, email, or login.",
            ),
            OpenApiParameter(
                name="department",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by direct department code.",
            ),
        ],
        responses={
            200: OrgEmployeeListSerializer(many=True),
            400: OpenApiResponse(description="Query parameter validation failed."),
            401: OpenApiResponse(description="Authentication is required."),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        serializer = OrgEmployeeQuerySerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)

        return filter_org_employees(
            org_employee_queryset(),
            search=serializer.validated_data.get("search", ""),
            department=serializer.validated_data.get("department", ""),
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["viewer_employee"] = get_optional_employee_for_user(self.request.user)

        return context
