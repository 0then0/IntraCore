from apps.legal.models import LegalDocument


def active_legal_documents_queryset():
    return (
        LegalDocument.objects.filter(active=True)
        .select_related("file")
        .order_by("document_type", "-published_at", "title")
    )
