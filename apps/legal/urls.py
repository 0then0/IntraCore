from django.urls import path

from apps.legal.views import LegalDocumentListView

urlpatterns = [
    path(
        "legal-documents/",
        LegalDocumentListView.as_view(),
        name="legal-document-list",
    ),
]
