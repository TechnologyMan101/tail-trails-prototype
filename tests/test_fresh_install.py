"""Exercise database installation and restarts against disposable on-disk databases."""

import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

from django.apps import apps
from django.conf import settings
from django.db import connection
from django.test import SimpleTestCase, TestCase


class FreshInstallTests(SimpleTestCase):
    def manage(self, database, *args):
        env = {**os.environ, "DB_ENGINE": "sqlite", "DATABASE_PATH": str(database)}
        return subprocess.run(
            [sys.executable, "manage.py", *args],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_fresh_install_restart_and_demo_seed_do_not_recreate_deleted_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "fresh.sqlite3"
            first = self.manage(database, "migrate", "--noinput")
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(self.manage(database, "seed_demo").returncode, 0)
            with sqlite3.connect(database) as db:
                self.assertEqual(
                    db.execute(
                        "SELECT name FROM django_migrations WHERE app='shelter'"
                    ).fetchall(),
                    [("0001_initial",)],
                )
                self.assertEqual(
                    db.execute("SELECT count(*) FROM shelter_animal").fetchone()[0], 4
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) FROM shelter_animal WHERE fleas_status='' OR heartworm_status=''"
                    ).fetchone()[0],
                    0,
                )
                db.execute(
                    "DELETE FROM shelter_animalphoto WHERE animal_id=(SELECT id FROM shelter_animal WHERE animal_id='TT-1004')"
                )
                db.execute("DELETE FROM shelter_animal WHERE animal_id='TT-1004'")
                db.execute(
                    "UPDATE shelter_animal SET status='Deceased',deceased_at='2026-11-17 12:00:00',deceased_by_id=(SELECT id FROM shelter_user LIMIT 1),deceased_reason='Natural causes' WHERE animal_id='TT-1001'"
                )
            restart = self.manage(database, "migrate", "--noinput")
            self.assertEqual(restart.returncode, 0, restart.stderr)
            self.assertEqual(self.manage(database, "seed_demo").returncode, 0)
            with sqlite3.connect(database) as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM shelter_animal").fetchone()[0], 3
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(
                        "UPDATE shelter_animal SET status='Available' WHERE animal_id='TT-1001'"
                    )

    def test_single_initial_schema(self):
        files = sorted(
            p.name for p in (settings.BASE_DIR / "shelter/migrations").glob("[0-9]*.py")
        )
        self.assertEqual(files, ["0001_initial.py"])


class SchemaTests(TestCase):
    def test_application_schema_matches_models(self):
        models = list(
            apps.get_app_config("shelter").get_models(include_auto_created=True)
        )
        tables = {model._meta.db_table for model in models}
        self.assertEqual(
            tables,
            {
                name
                for name in connection.introspection.table_names()
                if name.startswith("shelter_")
            },
        )
        with connection.cursor() as cursor:
            for model in models:
                columns = {
                    field.name
                    for field in connection.introspection.get_table_description(
                        cursor, model._meta.db_table
                    )
                }
                self.assertEqual(
                    columns, {field.column for field in model._meta.local_fields}
                )
