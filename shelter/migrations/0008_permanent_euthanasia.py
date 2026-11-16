from django.db import migrations


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION shelter_protect_euthanasia() RETURNS trigger AS $$
            BEGIN
                IF OLD.status = 'Euthanized' AND (
                    NEW.status IS DISTINCT FROM OLD.status OR
                    NEW.euthanized_at IS DISTINCT FROM OLD.euthanized_at OR
                    NEW.euthanized_by_id IS DISTINCT FROM OLD.euthanized_by_id
                ) THEN
                    RAISE EXCEPTION 'Confirmed euthanized status and confirmation details are permanent';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER shelter_permanent_euthanasia BEFORE UPDATE ON shelter_animal
            FOR EACH ROW EXECUTE FUNCTION shelter_protect_euthanasia();
        """)
    elif schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER shelter_permanent_euthanasia BEFORE UPDATE ON shelter_animal
            WHEN OLD.status = 'Euthanized' AND (
                NEW.status IS NOT OLD.status OR NEW.euthanized_at IS NOT OLD.euthanized_at OR
                NEW.euthanized_by_id IS NOT OLD.euthanized_by_id)
            BEGIN SELECT RAISE(ABORT, 'Confirmed euthanized status and confirmation details are permanent'); END;
        """)


def unprotect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER shelter_permanent_euthanasia ON shelter_animal; DROP FUNCTION shelter_protect_euthanasia();")
    elif schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER shelter_permanent_euthanasia;")


class Migration(migrations.Migration):
    dependencies = [("shelter", "0007_animal_euthanized_at_animal_euthanized_by_and_more")]
    operations = [migrations.RunPython(protect, unprotect)]
