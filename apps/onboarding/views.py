from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.employees.selectors import get_employee_for_user
from apps.onboarding.selectors import available_onboarding_items_queryset
from apps.onboarding.serializers import OnboardingItemSerializer
from apps.onboarding.services import mark_onboarding_item_viewed


class OnboardingAvailableListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OnboardingItemSerializer

    @extend_schema(
        tags=["Onboarding"],
        responses={
            200: OnboardingItemSerializer(many=True),
            401: OpenApiResponse(description="Authentication is required."),
            404: OpenApiResponse(description="Employee profile was not found."),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        employee = get_employee_for_user(self.request.user)
        return available_onboarding_items_queryset(employee)


class OnboardingViewedView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Onboarding"],
        request=None,
        responses={
            204: OpenApiResponse(description="Onboarding item was marked as viewed."),
            401: OpenApiResponse(description="Authentication is required."),
            404: OpenApiResponse(description="Onboarding item was not found."),
        },
    )
    def post(self, request, code: str):
        employee = get_employee_for_user(request.user)
        mark_onboarding_item_viewed(employee, code)

        return Response(status=status.HTTP_204_NO_CONTENT)
