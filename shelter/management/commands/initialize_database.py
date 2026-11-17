"""Create/reopen this baseline only; never upgrade an earlier prototype database."""

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder


BASELINE = "0001_fresh_baseline"


def require_current_baseline(connection):
    tables = set(connection.introspection.table_names())
    recorded = set()
    if MigrationRecorder.Migration._meta.db_table in tables:
        recorded = set(
            MigrationRecorder(connection)
            .migration_qs.filter(app="shelter")
            .values_list("name", flat=True)
        )
    incompatible = bool(tables) and recorded != {BASELINE}
    if recorded == {BASELINE}:
        models = list(
            apps.get_app_config("shelter").get_models(include_auto_created=True)
        )
        expected = {model._meta.db_table for model in models}
        incompatible = expected != {
            table for table in tables if table.startswith("shelter_")
        }
        if not incompatible:
            with connection.cursor() as cursor:
                for model in models:
                    columns = {
                        field.name
                        for field in connection.introspection.get_table_description(
                            cursor, model._meta.db_table
                        )
                    }
                    if columns != {field.column for field in model._meta.local_fields}:
                        incompatible = True
                        break
    if incompatible:
        raise CommandError(
            "This build supports fresh installations only. The database belongs to "
            "another prototype schema. Use a new, empty database/data folder; "
            "the existing database has not been modified."
        )


class Command(BaseCommand):
    help = "Initialize an empty database, or reopen this same fresh-install baseline."

    def handle(self, *args, **options):
        require_current_baseline(connections["default"])
        call_command(
            "migrate",
            interactive=False,
            stdout=self.stdout,
            stderr=self.stderr,
            verbosity=options["verbosity"],
        )
