from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.legal.selectors import active_legal_documents_queryset
from apps.legal.serializers import LegalDocumentSerializer


class LegalDocumentListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LegalDocumentSerializer

    @extend_schema(
        tags=["Legal Documents"],
        responses={
            200: LegalDocumentSerializer(many=True),
            401: OpenApiResponse(description="Authentication is required."),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return active_legal_documents_queryset()
