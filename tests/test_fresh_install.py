"""Exercise the actual fresh-install command against disposable on-disk databases."""

import hashlib
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
from django.urls import resolve, Resolver404


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
            first = self.manage(database, "initialize_database")
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(self.manage(database, "seed_demo").returncode, 0)
            with sqlite3.connect(database) as db:
                self.assertEqual(
                    db.execute(
                        "SELECT name FROM django_migrations WHERE app='shelter'"
                    ).fetchall(),
                    [("0001_fresh_baseline",)],
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
            restart = self.manage(database, "initialize_database")
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

    def test_prior_or_untracked_schema_is_refused_without_changing_data(self):
        for tracked in (True, False):
            with self.subTest(tracked=tracked), tempfile.TemporaryDirectory() as tmp:
                database = Path(tmp) / "old.sqlite3"
                with sqlite3.connect(database) as db:
                    db.execute(
                        "CREATE TABLE shelter_animal (id integer primary key, sentinel text)"
                    )
                    db.execute("INSERT INTO shelter_animal VALUES (1,'Preserve me')")
                    if tracked:
                        db.execute(
                            "CREATE TABLE django_migrations (id integer primary key, app text, name text, applied datetime)"
                        )
                        db.execute(
                            "INSERT INTO django_migrations VALUES (1,'shelter','0001_initial','2026-11-17 00:00:00')"
                        )
                before = hashlib.sha256(database.read_bytes()).digest()
                result = self.manage(database, "initialize_database")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("fresh installations only", result.stderr)
                self.assertEqual(hashlib.sha256(database.read_bytes()).digest(), before)

    def test_single_initial_schema_and_retired_routes(self):
        files = sorted(
            p.name for p in (settings.BASE_DIR / "shelter/migrations").glob("[0-9]*.py")
        )
        self.assertEqual(files, ["0001_fresh_baseline.py"])
        for path in ("/activity", "/animals/1/confirm-euthanized"):
            with self.assertRaises(Resolver404):
                resolve(path)


class BaselineSchemaTests(TestCase):
    def test_retired_columns_and_log_tables_are_absent(self):
        animal = apps.get_model("shelter", "Animal")
        fields = {f.name for f in animal._meta.get_fields()}
        columns = {
            f.name
            for f in connection.introspection.get_table_description(
                connection.cursor(), animal._meta.db_table
            )
        }
        for name in (
            "found_by",
            "spay_notes",
            "energy_level",
            "flea_prevention",
            "specific_location",
        ):
            self.assertNotIn(name, fields)
            self.assertNotIn(name, columns)
        self.assertIn("kennel_location", columns)
        for table in ("shelter_auditevent", "shelter_animalhistory"):
            self.assertNotIn(table, connection.introspection.table_names())
