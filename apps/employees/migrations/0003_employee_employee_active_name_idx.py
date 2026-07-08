from django.conf import settings
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("employees", "0002_employee_photo_moderated_at_and_more"),
        ("org", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="employee",
            index=models.Index(
                fields=["is_active", "last_name", "first_name"],
                name="employee_active_name_idx",
            ),
        ),
    ]
