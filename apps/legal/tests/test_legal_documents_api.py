from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from wagtail.documents import get_document_model
from wagtail.models import Collection

from apps.legal.models import LegalDocument

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="legal-reader",
        email="legal-reader@example.com",
        password="password",
    )


def create_wagtail_document(*, title: str, filename: str):
    document_model = get_document_model()
    root_collection = Collection.get_first_root_node()
    if root_collection is None:
        root_collection = Collection.add_root(name="Root")

    return document_model.objects.create(
        title=title,
        file=SimpleUploadedFile(
            filename,
            b"document content",
            content_type="application/pdf",
        ),
        collection=root_collection,
    )


def create_legal_document(
    *,
    document_type: str = LegalDocument.DocumentType.POLICY,
    title: str = "Policy",
    version: str = "1.0",
    active: bool = True,
    published_at=None,
):
    document = create_wagtail_document(
        title=title,
        filename=f"{document_type}-{version}.pdf",
    )

    return LegalDocument.objects.create(
        document_type=document_type,
        title=title,
        file=document,
        version=version,
        active=active,
        published_at=published_at or timezone.now(),
    )


def test_legal_documents_empty_list(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get(reverse("legal-document-list"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["results"] == []


def test_legal_documents_return_active_documents_only(api_client, user):
    active_document = create_legal_document(title="Active policy", version="1.0")
    create_legal_document(
        title="Inactive policy",
        version="2.0",
        active=False,
    )
    api_client.force_authenticate(user=user)

    response = api_client.get(reverse("legal-document-list"))

    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["title"] == active_document.title


def test_legal_document_response_contains_stable_file_url(api_client, user):
    create_legal_document(title="Policy", version="1.0")
    api_client.force_authenticate(user=user)

    response = api_client.get(reverse("legal-document-list"))

    assert response.status_code == status.HTTP_200_OK
    file_url = response.json()["results"][0]["file_url"]
    assert file_url.startswith("http://testserver/media/")
    assert file_url.endswith(".pdf")


def test_legal_documents_are_ordered_by_type_and_published_date(api_client, user):
    now = timezone.now()
    create_legal_document(
        document_type=LegalDocument.DocumentType.POLICY,
        title="Older policy",
        version="1.0",
        published_at=now - timedelta(days=1),
    )
    create_legal_document(
        document_type=LegalDocument.DocumentType.POLICY,
        title="Newer policy",
        version="2.0",
        published_at=now,
    )
    create_legal_document(
        document_type=LegalDocument.DocumentType.AGREEMENT,
        title="Agreement",
        version="1.0",
        published_at=now,
    )
    api_client.force_authenticate(user=user)

    response = api_client.get(reverse("legal-document-list"))

    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    assert [item["title"] for item in results] == [
        "Agreement",
        "Newer policy",
        "Older policy",
    ]


def test_anonymous_user_cannot_read_legal_documents(api_client):
    response = api_client.get(reverse("legal-document-list"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
