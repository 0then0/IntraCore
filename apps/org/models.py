from django.db import models


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
        indexes = [
            models.Index(fields=["parent", "name"]),
        ]

    def __str__(self) -> str:
        return self.name
