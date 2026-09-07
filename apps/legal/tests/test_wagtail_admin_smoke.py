import pytest

pytestmark = pytest.mark.django_db


def test_wagtail_admin_requires_login(client):
    response = client.get("/cms/")

    assert response.status_code == 302
    assert "/cms/login/" in response["Location"]


def test_wagtail_photo_moderation_requires_login(client):
    response = client.get("/cms/photo-moderation/")

    assert response.status_code == 302
    assert "/cms/login/" in response["Location"]


def test_wagtail_photo_moderation_renders_for_admin(client, django_user_model):
    admin = django_user_model.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="password",
    )
    client.force_login(admin)

    response = client.get("/cms/photo-moderation/")

    assert response.status_code == 200
    assert "Photo moderation" in response.content.decode()
