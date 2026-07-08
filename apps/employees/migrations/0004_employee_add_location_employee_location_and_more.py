from django.db import migrations, models


def _set_location_defaults_sql() -> str:
    return """
        ALTER TABLE employees_employee
        ALTER COLUMN add_location SET DEFAULT '';
        ALTER TABLE employees_employee
        ALTER COLUMN location_city SET DEFAULT '';
        ALTER TABLE employees_employee
        ALTER COLUMN location SET DEFAULT '';
    """


def _drop_location_defaults_sql() -> str:
    return """
        ALTER TABLE employees_employee
        ALTER COLUMN add_location DROP DEFAULT;
        ALTER TABLE employees_employee
        ALTER COLUMN location_city DROP DEFAULT;
        ALTER TABLE employees_employee
        ALTER COLUMN location DROP DEFAULT;
    """


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("employees", "0003_employee_employee_active_name_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="add_location",
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name="employee",
            name="location",
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name="employee",
            name="location_city",
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.RunSQL(
            sql=_set_location_defaults_sql(),
            reverse_sql=_drop_location_defaults_sql(),
        ),
        migrations.AlterField(
            model_name="employee",
            name="education",
            field=models.CharField(blank=True, max_length=2500),
        ),
    ]
