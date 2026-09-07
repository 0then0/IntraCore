from datetime import date
from io import StringIO

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import CommandError, call_command

from apps.employees.models import Employee, private_pending_photo_storage

pytestmark = pytest.mark.django_db


def test_migrate_pending_photos_copies_and_deletes_public_source(
    django_user_model,
    settings,
    tmp_path,
):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.PRIVATE_PHOTO_ROOT = tmp_path / "private"
    private_pending_photo_storage._location = str(settings.PRIVATE_PHOTO_ROOT)
    private_pending_photo_storage.__dict__.pop("base_location", None)
    private_pending_photo_storage.__dict__.pop("location", None)
    user = django_user_model.objects.create_user(
        username="employee",
        email="employee@example.com",
        password="password",
    )
    name = default_storage.save(
        "employees/pending_photos/pending.png",
        ContentFile(b"pending-photo"),
    )
    Employee.objects.create(
        user=user,
        email="employee@example.com",
        login="employee",
        first_name="First",
        last_name="Last",
        pending_photo=name,
        hired_at=date(2020, 1, 10),
    )

    call_command("migrate_pending_photos", delete_source=True, stdout=StringIO())

    assert private_pending_photo_storage.exists(name)
    assert not default_storage.exists(name)


def test_migrate_pending_photos_keeps_public_sources_when_a_copy_fails(
    django_user_model,
    settings,
    tmp_path,
):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.PRIVATE_PHOTO_ROOT = tmp_path / "private"
    private_pending_photo_storage._location = str(settings.PRIVATE_PHOTO_ROOT)
    private_pending_photo_storage.__dict__.pop("base_location", None)
    private_pending_photo_storage.__dict__.pop("location", None)
    first_user = django_user_model.objects.create_user(
        username="first",
        email="first@example.com",
        password="password",
    )
    second_user = django_user_model.objects.create_user(
        username="second",
        email="second@example.com",
        password="password",
    )
    existing_name = default_storage.save(
        "employees/pending_photos/existing.png",
        ContentFile(b"existing-photo"),
    )
    Employee.objects.create(
        user=first_user,
        email="first@example.com",
        login="first",
        first_name="First",
        last_name="Employee",
        pending_photo=existing_name,
        hired_at=date(2020, 1, 10),
    )
    Employee.objects.create(
        user=second_user,
        email="second@example.com",
        login="second",
        first_name="Second",
        last_name="Employee",
        pending_photo="employees/pending_photos/missing.png",
        hired_at=date(2020, 1, 10),
    )

    with pytest.raises(CommandError, match="Public source file is missing"):
        call_command("migrate_pending_photos", delete_source=True, stdout=StringIO())

    assert default_storage.exists(existing_name)
    assert private_pending_photo_storage.private_exists(existing_name)
