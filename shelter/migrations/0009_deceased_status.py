import importlib
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


old = importlib.import_module('shelter.migrations.0008_permanent_euthanasia')


def forward(apps, schema_editor):
    apps.get_model('shelter', 'Animal').objects.filter(status='Euthanized').update(status='Deceased', deceased_reason='Previously recorded as euthanized.')


def backward(apps, schema_editor):
    apps.get_model('shelter', 'Animal').objects.filter(status='Deceased').update(status='Euthanized')


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("""
        CREATE FUNCTION shelter_protect_deceased() RETURNS trigger AS $$
        BEGIN
            IF OLD.status = 'Deceased' AND (NEW.status IS DISTINCT FROM OLD.status OR
            NEW.deceased_at IS DISTINCT FROM OLD.deceased_at OR NEW.deceased_by_id IS DISTINCT FROM OLD.deceased_by_id OR
            NEW.deceased_reason IS DISTINCT FROM OLD.deceased_reason) THEN
                RAISE EXCEPTION 'Confirmed deceased status, reason and confirmation details are permanent';
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER shelter_permanent_deceased BEFORE UPDATE ON shelter_animal FOR EACH ROW EXECUTE FUNCTION shelter_protect_deceased();
        """)
    elif schema_editor.connection.vendor == 'sqlite':
        schema_editor.execute("""CREATE TRIGGER shelter_permanent_deceased BEFORE UPDATE ON shelter_animal
        WHEN OLD.status = 'Deceased' AND (NEW.status IS NOT OLD.status OR NEW.deceased_at IS NOT OLD.deceased_at OR
        NEW.deceased_by_id IS NOT OLD.deceased_by_id OR NEW.deceased_reason IS NOT OLD.deceased_reason)
        BEGIN SELECT RAISE(ABORT, 'Confirmed deceased status, reason and confirmation details are permanent'); END;""")


def unprotect(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('DROP TRIGGER shelter_permanent_deceased ON shelter_animal; DROP FUNCTION shelter_protect_deceased();')
    elif schema_editor.connection.vendor == 'sqlite':
        schema_editor.execute('DROP TRIGGER shelter_permanent_deceased;')


class Migration(migrations.Migration):
    dependencies = [('shelter', '0008_permanent_euthanasia')]
    operations = [
        migrations.RunPython(old.unprotect, old.protect),
        migrations.RenameField('animal', 'euthanized_at', 'deceased_at'),
        migrations.RenameField('animal', 'euthanized_by', 'deceased_by'),
        migrations.AddField('animal', 'deceased_reason', models.TextField(blank=True, editable=False)),
        migrations.AlterField('animal', 'deceased_by', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='confirmed_deceased_records', to=settings.AUTH_USER_MODEL)),
        migrations.AlterField('animal', 'status', models.CharField(max_length=30, choices=[(s, s) for s in ('Available', 'Pending Adoption', 'Not Available', 'Deceased')])),
        migrations.RunPython(forward, backward),
        migrations.RunPython(protect, unprotect),
    ]
