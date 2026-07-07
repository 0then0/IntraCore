from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.snippets.models import register_snippet


@register_snippet
class OnboardingItem(models.Model):
    class Audience(models.TextChoices):
        ALL = "all", "All employees"
        NEW_HIRES = "new_hires", "New hires"
        MANAGERS = "managers", "Managers"

    code = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=200)
    body = RichTextField(blank=True)
    release_date = models.DateField()
    active = models.BooleanField(default=False)
    audience = models.CharField(
        max_length=32,
        choices=Audience.choices,
        default=Audience.ALL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    panels = [
        FieldPanel("code"),
        FieldPanel("title"),
        FieldPanel("body"),
        FieldPanel("release_date"),
        FieldPanel("active"),
        FieldPanel("audience"),
    ]

    class Meta:
        indexes = [
            models.Index(fields=["active", "release_date"]),
        ]

    def __str__(self) -> str:
        return self.title


class ViewedOnboardingItem(models.Model):
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="viewed_onboarding_items",
        related_query_name="viewed_onboarding_item",
    )
    onboarding_item = models.ForeignKey(
        OnboardingItem,
        on_delete=models.CASCADE,
        related_name="views",
        related_query_name="view",
    )
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "onboarding_item"],
                name="unique_viewed_onboarding_item",
            ),
        ]
        indexes = [
            models.Index(fields=["employee", "viewed_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.employee_id}:{self.onboarding_item_id}"
