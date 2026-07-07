from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.documents import get_document_model_string
from wagtail.snippets.models import register_snippet


@register_snippet
class LegalDocument(models.Model):
    class DocumentType(models.TextChoices):
        POLICY = "policy", "Policy"
        AGREEMENT = "agreement", "Agreement"
        NOTICE = "notice", "Notice"
        OTHER = "other", "Other"

    document_type = models.CharField(max_length=32, choices=DocumentType.choices)
    title = models.CharField(max_length=200)
    file = models.ForeignKey(
        get_document_model_string(),
        on_delete=models.PROTECT,
        related_name="legal_documents",
        related_query_name="legal_document",
    )
    version = models.CharField(max_length=32)
    active = models.BooleanField(default=False)
    published_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    panels = [
        FieldPanel("document_type"),
        FieldPanel("title"),
        FieldPanel("file"),
        FieldPanel("version"),
        FieldPanel("active"),
        FieldPanel("published_at"),
    ]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document_type", "version"],
                name="legal_document_unique_type_version",
            ),
        ]
        indexes = [
            models.Index(fields=["active", "document_type", "-published_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} v{self.version}"
