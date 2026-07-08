from django.db import migrations, models


def _set_not_null_sql(column_name: str, constraint_name: str) -> str:
    return f"""
        ALTER TABLE employees_employee
        ADD CONSTRAINT {constraint_name}
        CHECK ({column_name} IS NOT NULL) NOT VALID;
        ALTER TABLE employees_employee
        VALIDATE CONSTRAINT {constraint_name};
        ALTER TABLE employees_employee
        ALTER COLUMN {column_name} SET NOT NULL;
        ALTER TABLE employees_employee
        DROP CONSTRAINT {constraint_name};
    """


def _drop_not_null_sql(column_name: str) -> str:
    return f"""
        ALTER TABLE employees_employee
        ALTER COLUMN {column_name} DROP NOT NULL;
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


def _set_location_defaults_sql() -> str:
    return """
        ALTER TABLE employees_employee
        ALTER COLUMN add_location SET DEFAULT '';
        ALTER TABLE employees_employee
        ALTER COLUMN location_city SET DEFAULT '';
        ALTER TABLE employees_employee
        ALTER COLUMN location SET DEFAULT '';
    """


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("employees", "0005_backfill_employee_location_fields"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=_set_not_null_sql(
                        "add_location",
                        "employee_add_location_not_null",
                    ),
                    reverse_sql=_drop_not_null_sql("add_location"),
                ),
                migrations.RunSQL(
                    sql=_set_not_null_sql(
                        "location_city",
                        "employee_location_city_not_null",
                    ),
                    reverse_sql=_drop_not_null_sql("location_city"),
                ),
                migrations.RunSQL(
                    sql=_set_not_null_sql(
                        "location",
                        "employee_location_not_null",
                    ),
                    reverse_sql=_drop_not_null_sql("location"),
                ),
                migrations.RunSQL(
                    sql=_drop_location_defaults_sql(),
                    reverse_sql=_set_location_defaults_sql(),
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="employee",
                    name="add_location",
                    field=models.CharField(blank=True, max_length=120),
                ),
                migrations.AlterField(
                    model_name="employee",
                    name="location_city",
                    field=models.CharField(blank=True, max_length=120),
                ),
                migrations.AlterField(
                    model_name="employee",
                    name="location",
                    field=models.CharField(blank=True, max_length=120),
                ),
            ],
        ),
    ]
