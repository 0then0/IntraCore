from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.serializers import HealthResponseSerializer


class HealthView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["System"],
        responses={200: HealthResponseSerializer},
    )
    def get(self, request):
        return Response({"status": "ok"})
