from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers

from apps.legal.models import LegalDocument


class LegalDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = LegalDocument
        fields = (
            "document_type",
            "title",
            "version",
            "file_url",
            "published_at",
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_file_url(self, legal_document: LegalDocument) -> str:
        request = self.context.get("request")
        url = legal_document.file.file.url

        if request is None:
            return url

        return request.build_absolute_uri(url)
