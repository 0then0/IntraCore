from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.employees.storage import PrivatePendingPhotoStorage

private_pending_photo_storage = PrivatePendingPhotoStorage()


class Employee(models.Model):
    employee_uuid = models.UUIDField(default=uuid4, unique=True, editable=False)
    external_id = models.CharField(max_length=64, blank=True, null=True, unique=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="employee_profile",
    )
    email = models.EmailField(max_length=254, unique=True)
    login = models.CharField(max_length=150, unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    middle_name = models.CharField(max_length=150, blank=True)
    position = models.CharField(max_length=150, blank=True)
    department = models.ForeignKey(
        "org.Department",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="employees",
        related_query_name="employee",
    )
    manager = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="direct_reports",
        related_query_name="direct_report",
    )
    hrbp = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="hrbp_profiles",
        related_query_name="hrbp_profile",
    )
    phone = models.CharField(max_length=32, blank=True)
    is_phone_visible = models.BooleanField(default=False)
    birthdate = models.DateField(blank=True, null=True)
    is_birthdate_visible = models.BooleanField(default=False)
    telegram_username = models.CharField(max_length=64, blank=True)
    city = models.CharField(max_length=120, blank=True)
    add_location = models.CharField(max_length=120, blank=True)
    location_city = models.CharField(max_length=120, blank=True)
    location = models.CharField(max_length=120, blank=True)
    about = models.TextField(max_length=2500, blank=True)
    hobbies = models.TextField(max_length=2500, blank=True)
    education = models.CharField(max_length=2500, blank=True)
    current_photo = models.FileField(
        blank=True,
        upload_to="employees/current_photos/",
    )
    pending_photo = models.FileField(
        blank=True,
        upload_to="employees/pending_photos/",
        storage=private_pending_photo_storage,
    )
    pending_photo_uploaded_at = models.DateTimeField(blank=True, null=True)
    photo_rejection_reason = models.TextField(max_length=500, blank=True)
    photo_moderated_at = models.DateTimeField(blank=True, null=True)
    photo_rejection_email_sent_at = models.DateTimeField(blank=True, null=True)
    hired_at = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(manager_id__isnull=True) | ~Q(manager_id=F("id")),
                name="employee_manager_is_not_self",
            ),
            models.CheckConstraint(
                condition=Q(hrbp_id__isnull=True) | ~Q(hrbp_id=F("id")),
                name="employee_hrbp_is_not_self",
            ),
        ]
        indexes = [
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["department", "is_active"]),
            models.Index(
                fields=["is_active", "last_name", "first_name"],
                name="employee_active_name_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} <{self.email}>"

    @property
    def full_name(self) -> str:
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(part for part in parts if part)

    @property
    def has_pending_photo(self) -> bool:
        return bool(self.pending_photo)

    @property
    def effective_city(self) -> str:
        return self.add_location or self.location_city or self.location or self.city


class PhotoRejectionNotification(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="photo_rejection_notifications",
    )
    recipient_email = models.EmailField(max_length=254)
    reason = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    delivery_claimed_at = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["sent_at", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Photo rejection notification {self.pk} for {self.employee_id}"
