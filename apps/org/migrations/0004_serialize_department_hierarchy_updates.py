from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("org", "0003_department_prevent_hierarchy_cycles"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION org_prevent_department_hierarchy_cycle()
                RETURNS trigger AS $$
                BEGIN
                    PERFORM pg_advisory_xact_lock(73501001);

                    IF NEW.parent_id IS NULL THEN
                        RETURN NEW;
                    END IF;

                    IF EXISTS (
                        WITH RECURSIVE ancestors AS (
                            SELECT id, parent_id
                            FROM org_department
                            WHERE id = NEW.parent_id

                            UNION

                            SELECT department.id, department.parent_id
                            FROM org_department AS department
                            INNER JOIN ancestors
                                ON department.id = ancestors.parent_id
                        )
                        SELECT 1
                        FROM ancestors
                        WHERE id = NEW.id
                    ) THEN
                        RAISE EXCEPTION 'Department hierarchy cannot contain a cycle'
                            USING ERRCODE = '23514';
                    END IF;

                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
