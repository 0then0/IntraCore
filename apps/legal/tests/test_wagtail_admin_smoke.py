import pytest

pytestmark = pytest.mark.django_db


def test_wagtail_admin_requires_login(client):
    response = client.get("/cms/")

    assert response.status_code == 302
    assert "/cms/login/" in response["Location"]
