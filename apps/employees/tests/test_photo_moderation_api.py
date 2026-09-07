from base64 import b64decode
from datetime import date

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.employees.models import (
    Employee,
    PhotoRejectionNotification,
    private_pending_photo_storage,
)
from apps.employees.tasks import (
    delete_current_photo_file,
    delete_pending_photo_file,
    send_photo_rejection_email,
)
from apps.integrations.exceptions import CaptchaUnavailableError

pytestmark = pytest.mark.django_db

PNG_1X1_BYTES = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4"
    "//8/AAX+Av4N70a4AAAAAElFTkSuQmCC"
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.PRIVATE_PHOTO_ROOT = tmp_path / "private"
    private_pending_photo_storage._location = str(settings.PRIVATE_PHOTO_ROOT)
    private_pending_photo_storage.__dict__.pop("base_location", None)
    private_pending_photo_storage.__dict__.pop("location", None)
    return tmp_path


def image_upload(name: str = "avatar.png") -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name,
        PNG_1X1_BYTES,
        content_type="image/png",
    )


def create_user(django_user_model, *, username: str, is_staff: bool = False):
    return django_user_model.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="password",
        is_staff=is_staff,
    )


def create_employee(
    django_user_model,
    *,
    login: str,
    current_photo=None,
    pending_photo=None,
) -> Employee:
    user = create_user(django_user_model, username=login)

    return Employee.objects.create(
        user=user,
        email=f"{login}@example.com",
        login=login,
        first_name="First",
        last_name="Last",
        current_photo=current_photo,
        pending_photo=pending_photo,
        pending_photo_uploaded_at=timezone.now() if pending_photo else None,
        hired_at=date(2020, 1, 10),
    )


def approve_url(employee: Employee) -> str:
    return reverse(
        "admin-photo-moderation-approve",
        kwargs={"employee_id": employee.employee_uuid},
    )


def reject_url(employee: Employee) -> str:
    return reverse(
        "admin-photo-moderation-reject",
        kwargs={"employee_id": employee.employee_uuid},
    )


def test_user_upload_saves_pending_photo_without_replacing_current_photo(
    api_client,
    django_user_model,
    media_root,
):
    employee = create_employee(
        django_user_model,
        login="owner",
        current_photo=image_upload("current.png"),
    )
    current_photo_name = employee.current_photo.name
    api_client.force_authenticate(user=employee.user)

    response = api_client.post(
        reverse("profile-photo-upload"),
        {"photo": image_upload("pending.png")},
        format="multipart",
    )

    assert response.status_code == status.HTTP_200_OK
    employee.refresh_from_db()
    data = response.json()
    assert employee.current_photo.name == current_photo_name
    assert employee.pending_photo
    assert employee.pending_photo_uploaded_at is not None
    assert data["has_pending_photo"] is True


def test_repeated_photo_upload_is_blocked(
    api_client,
    django_user_model,
    media_root,
):
    employee = create_employee(
        django_user_model,
        login="owner",
        pending_photo=image_upload("pending.png"),
    )
    api_client.force_authenticate(user=employee.user)

    response = api_client.post(
        reverse("profile-photo-upload"),
        {"photo": image_upload("another.png")},
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "photo" in response.json()


def test_admin_approve_replaces_current_photo(
    api_client,
    django_user_model,
    media_root,
    mocker,
    django_capture_on_commit_callbacks,
):
    staff_user = create_user(django_user_model, username="admin", is_staff=True)
    employee = create_employee(
        django_user_model,
        login="employee",
        current_photo=image_upload("current.png"),
        pending_photo=image_upload("pending.png"),
    )
    delete_pending = mocker.patch.object(delete_pending_photo_file, "delay")
    delete_current = mocker.patch.object(delete_current_photo_file, "delay")
    api_client.force_authenticate(user=staff_user)

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(approve_url(employee))

    assert response.status_code == status.HTTP_200_OK
    employee.refresh_from_db()
    assert employee.current_photo.name.startswith("employees/current_photos/")
    assert not employee.pending_photo
    assert employee.pending_photo_uploaded_at is None
    delete_pending.assert_called_once()
    delete_current.assert_called_once()


def test_admin_reject_requires_reason(
    api_client,
    django_user_model,
    media_root,
):
    staff_user = create_user(django_user_model, username="admin", is_staff=True)
    employee = create_employee(
        django_user_model,
        login="employee",
        pending_photo=image_upload("pending.png"),
    )
    api_client.force_authenticate(user=staff_user)

    response = api_client.post(reject_url(employee), {}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "reason" in response.json()
    employee.refresh_from_db()
    assert employee.pending_photo


def test_admin_reject_enqueues_email_task_after_commit(
    api_client,
    django_user_model,
    media_root,
    mocker,
    django_capture_on_commit_callbacks,
):
    staff_user = create_user(django_user_model, username="admin", is_staff=True)
    employee = create_employee(
        django_user_model,
        login="employee",
        pending_photo=image_upload("pending.png"),
    )
    delay = mocker.patch.object(send_photo_rejection_email, "delay")
    delete_pending = mocker.patch.object(delete_pending_photo_file, "delay")
    api_client.force_authenticate(user=staff_user)

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            reject_url(employee),
            {"reason": "Low image quality."},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    notification = PhotoRejectionNotification.objects.get(employee=employee)
    delay.assert_called_once_with(notification.pk)
    delete_pending.assert_called_once()


def test_pending_photo_is_not_exposed_to_other_user(
    api_client,
    django_user_model,
    media_root,
):
    viewer = create_employee(django_user_model, login="viewer")
    target = create_employee(
        django_user_model,
        login="target",
        pending_photo=image_upload("pending.png"),
    )
    api_client.force_authenticate(user=viewer.user)

    response = api_client.get(
        reverse("employee-detail", kwargs={"id": target.employee_uuid}),
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["has_pending_photo"] is False
    assert data["pending_photo_uploaded_at"] is None
    assert "pending_photo_url" not in data


def test_owner_can_see_pending_photo_status(
    api_client,
    django_user_model,
    media_root,
):
    employee = create_employee(
        django_user_model,
        login="owner",
        pending_photo=image_upload("pending.png"),
    )
    api_client.force_authenticate(user=employee.user)

    response = api_client.get(reverse("profile-me"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["has_pending_photo"] is True
    assert response.json()["pending_photo_uploaded_at"] is not None


def test_non_staff_user_cannot_access_photo_moderation(
    api_client,
    django_user_model,
):
    employee = create_employee(django_user_model, login="employee")
    api_client.force_authenticate(user=employee.user)

    list_response = api_client.get(reverse("admin-photo-moderation-list"))
    approve_response = api_client.post(approve_url(employee))
    pending_response = api_client.get(
        reverse(
            "admin-photo-moderation-pending-photo",
            kwargs={"employee_id": employee.employee_uuid},
        ),
    )

    assert list_response.status_code == status.HTTP_403_FORBIDDEN
    assert approve_response.status_code == status.HTTP_403_FORBIDDEN
    assert pending_response.status_code == status.HTTP_403_FORBIDDEN


def test_approve_is_idempotent(api_client, django_user_model, media_root):
    staff_user = create_user(django_user_model, username="admin", is_staff=True)
    employee = create_employee(
        django_user_model,
        login="employee",
        pending_photo=image_upload("pending.png"),
    )
    api_client.force_authenticate(user=staff_user)

    first_response = api_client.post(approve_url(employee))
    second_response = api_client.post(approve_url(employee))

    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_200_OK
    employee.refresh_from_db()
    assert employee.current_photo
    assert not employee.pending_photo


def test_reject_is_idempotent(
    api_client,
    django_user_model,
    media_root,
    mocker,
    django_capture_on_commit_callbacks,
):
    staff_user = create_user(django_user_model, username="admin", is_staff=True)
    employee = create_employee(
        django_user_model,
        login="employee",
        pending_photo=image_upload("pending.png"),
    )
    delay = mocker.patch.object(send_photo_rejection_email, "delay")
    mocker.patch.object(delete_pending_photo_file, "delay")
    api_client.force_authenticate(user=staff_user)

    with django_capture_on_commit_callbacks(execute=True):
        first_response = api_client.post(
            reject_url(employee),
            {"reason": "Low image quality."},
            format="json",
        )
        second_response = api_client.post(
            reject_url(employee),
            {"reason": "Low image quality."},
            format="json",
        )

    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_200_OK
    employee.refresh_from_db()
    assert not employee.pending_photo
    assert employee.photo_rejection_reason == "Low image quality."
    notification = PhotoRejectionNotification.objects.get(employee=employee)
    delay.assert_called_once_with(notification.pk)


def test_pending_photo_storage_is_not_public(
    api_client,
    django_user_model,
    media_root,
):
    employee = create_employee(
        django_user_model,
        login="owner",
        pending_photo=image_upload("pending.png"),
    )

    response = api_client.get(employee.pending_photo.url)

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_staff_can_read_legacy_pending_photo_during_storage_rollout(
    api_client,
    django_user_model,
    media_root,
):
    staff_user = create_user(django_user_model, username="admin", is_staff=True)
    legacy_photo_name = default_storage.save(
        "employees/pending_photos/legacy.png",
        ContentFile(PNG_1X1_BYTES),
    )
    employee = create_employee(
        django_user_model,
        login="employee",
        pending_photo=legacy_photo_name,
    )
    api_client.force_authenticate(user=staff_user)

    response = api_client.get(
        reverse(
            "admin-photo-moderation-pending-photo",
            kwargs={"employee_id": employee.employee_uuid},
        ),
    )

    assert response.status_code == status.HTTP_200_OK
    assert b"".join(response.streaming_content) == PNG_1X1_BYTES


def test_approve_is_idempotent_when_pending_photo_is_rejected_during_copy(
    api_client,
    django_user_model,
    media_root,
    mocker,
):
    staff_user = create_user(django_user_model, username="admin", is_staff=True)
    employee = create_employee(
        django_user_model,
        login="employee",
        pending_photo=image_upload("pending.png"),
    )
    api_client.force_authenticate(user=staff_user)

    def reject_before_copy(_pending_photo):
        Employee.objects.filter(pk=employee.pk).update(
            pending_photo="",
            pending_photo_uploaded_at=None,
        )
        raise FileNotFoundError

    mocker.patch(
        "apps.employees.services._copy_pending_photo_to_current_storage",
        side_effect=reject_before_copy,
    )

    response = api_client.post(approve_url(employee))

    assert response.status_code == status.HTTP_200_OK
    employee.refresh_from_db()
    assert not employee.pending_photo


def test_approve_returns_validation_error_when_pending_file_is_missing(
    api_client,
    django_user_model,
    media_root,
    mocker,
):
    staff_user = create_user(django_user_model, username="admin", is_staff=True)
    employee = create_employee(
        django_user_model,
        login="employee",
        pending_photo=image_upload("pending.png"),
    )
    api_client.force_authenticate(user=staff_user)
    mocker.patch(
        "apps.employees.services._copy_pending_photo_to_current_storage",
        side_effect=FileNotFoundError,
    )

    response = api_client.post(approve_url(employee))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "photo" in response.json()


def test_photo_upload_returns_controlled_error_when_captcha_is_unavailable(
    api_client,
    django_user_model,
    media_root,
    mocker,
):
    employee = create_employee(django_user_model, login="owner")
    api_client.force_authenticate(user=employee.user)
    mocker.patch(
        "apps.employees.views.upload_pending_photo",
        side_effect=CaptchaUnavailableError(),
    )

    response = api_client.post(
        reverse("profile-photo-upload"),
        {"photo": image_upload("pending.png")},
        format="multipart",
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {
        "code": "captcha_unavailable",
        "detail": "Captcha verification is unavailable.",
    }


def test_staff_can_download_pending_photo_through_protected_endpoint(
    api_client,
    django_user_model,
    media_root,
):
    staff_user = create_user(django_user_model, username="admin", is_staff=True)
    employee = create_employee(
        django_user_model,
        login="employee",
        pending_photo=image_upload("pending.png"),
    )
    api_client.force_authenticate(user=staff_user)

    response = api_client.get(
        reverse(
            "admin-photo-moderation-pending-photo",
            kwargs={"employee_id": employee.employee_uuid},
        ),
    )

    assert response.status_code == status.HTTP_200_OK
    assert b"".join(response.streaming_content) == PNG_1X1_BYTES
