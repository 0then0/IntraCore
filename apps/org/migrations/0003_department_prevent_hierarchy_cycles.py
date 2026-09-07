from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("org", "0002_department_department_parent_is_not_self"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE FUNCTION org_prevent_department_hierarchy_cycle()
                RETURNS trigger AS $$
                BEGIN
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

                CREATE TRIGGER org_prevent_department_hierarchy_cycle
                BEFORE INSERT OR UPDATE OF parent_id ON org_department
                FOR EACH ROW
                EXECUTE FUNCTION org_prevent_department_hierarchy_cycle();
            """,
            reverse_sql="""
                DROP TRIGGER org_prevent_department_hierarchy_cycle
                ON org_department;

                DROP FUNCTION org_prevent_department_hierarchy_cycle();
            """,
        ),
    ]
