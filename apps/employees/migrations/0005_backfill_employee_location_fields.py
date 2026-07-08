from django.db import migrations, transaction
from django.db.models import Q

BATCH_SIZE = 1000
LOCATION_FIELDS = ("add_location", "location_city", "location")


def backfill_location_fields(apps, schema_editor):
    Employee = apps.get_model("employees", "Employee")

    while True:
        employee_ids = list(
            Employee.objects.filter(
                Q(add_location__isnull=True)
                | Q(location_city__isnull=True)
                | Q(location__isnull=True),
            )
            .order_by("pk")
            .values_list("pk", flat=True)[:BATCH_SIZE],
        )
        if not employee_ids:
            break

        with transaction.atomic():
            for field_name in LOCATION_FIELDS:
                Employee.objects.filter(
                    pk__in=employee_ids,
                    **{f"{field_name}__isnull": True},
                ).update(**{field_name: ""})


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("employees", "0004_employee_add_location_employee_location_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_location_fields,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
