from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Department(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=150)
    parent = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="children",
        related_query_name="child",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(parent_id__isnull=True) | ~Q(parent_id=F("id")),
                name="department_parent_is_not_self",
            ),
        ]
        indexes = [
            models.Index(fields=["parent", "name"]),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()

        parent = self.parent
        visited_department_ids = set()

        while parent is not None:
            if parent.pk == self.pk or parent.pk in visited_department_ids:
                raise ValidationError(
                    {"parent": "Department hierarchy cannot contain a cycle."},
                )

            if parent.pk is not None:
                visited_department_ids.add(parent.pk)
            parent = parent.parent
