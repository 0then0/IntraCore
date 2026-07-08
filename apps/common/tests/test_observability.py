import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


def test_health_endpoint_returns_ok():
    response = APIClient().get(reverse("health"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


def test_request_id_header_is_generated_when_missing():
    response = APIClient().get(reverse("health"))

    request_id = response["X-Request-ID"]
    uuid.UUID(request_id)


def test_request_id_header_is_reused_when_provided():
    response = APIClient().get(
        reverse("health"),
        HTTP_X_REQUEST_ID="request-id-123",
    )

    assert response["X-Request-ID"] == "request-id-123"


def test_request_id_header_replaces_too_long_value():
    response = APIClient().get(
        reverse("health"),
        HTTP_X_REQUEST_ID="x" * 129,
    )

    request_id = response["X-Request-ID"]
    assert request_id != "x" * 129
    uuid.UUID(request_id)


def test_request_id_header_is_added_to_api_errors():
    response = APIClient().get(
        reverse("profile-me"),
        HTTP_X_REQUEST_ID="request-id-456",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response["X-Request-ID"] == "request-id-456"


def test_openapi_schema_contains_health_path():
    response = APIClient().get(reverse("schema"))

    assert response.status_code == status.HTTP_200_OK
    assert "/health/" in response.content.decode()
