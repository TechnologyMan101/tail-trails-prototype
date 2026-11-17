# Contributing to Tail Trails

This repository is a fresh-install-only prototype baseline. Use a new database and upload directory; earlier prototype databases are unsupported. The single initial Django schema creates only current models and the permanent deceased-status trigger. Do not copy old migration chains back into this baseline or use `--fake` to attach old data.

## Source map

- `shelter/models.py`: users, organization, animals, photos, submissions, crop batches and hours.
- `shelter/forms.py`: field validation, conditional requirements and unsigned numeric controls.
- `shelter/views.py` / `urls.py`: role checks and application workflows.
- `shelter/photo_batches.py`: private pending uploads, deadlines, cancellation and finalization.
- `shelter/images.py` / `branding_images.py`: crop-based image generation and retained sources.
- `shelter/branding.py`: browser-icon generation and fallback.
- `shelter/diagnostics.py`: read-only system information.
- `templates/` / `static/`: server-rendered HTML, CSS and JavaScript.
- `tests/`: integration, fresh-install and numeric-input checks.
- `tools/build_overview.py`: optional architecture PDF generator.

## Making a change

1. Branch from the team's current base using `GIT_WORKFLOW.md`.
2. State the intended behavior and roles affected before changing shared workflows.
3. Put authoritative validation/permissions on the server. Browser controls improve usability but do not replace server checks.
4. Review model/schema changes together. Commit the schema definition and its reviewed Django migration representation with the code; a future upgrade policy must be agreed explicitly before promising compatibility.
5. Run checks appropriate to the change, including a new empty-database install for schema/startup changes. Keep permanent deceased-status protection covered at model and database levels.
6. Update README/PDF narrative when behavior changes. Bump `VERSION` for a release, then tag the reviewed commit.

Install the locked dependencies and run:

```bash
DB_ENGINE=sqlite python manage.py test
DB_ENGINE=sqlite python manage.py makemigrations --check --dry-run
node --check static/app.js
node tests/test_unsigned_inputs.js
```

SQLite is useful for isolated tests; smoke-test the Compose/PostgreSQL deployment when available. Do not commit `.env`, actual uploads/database folders, collected static files or Python environments. Avoid unrelated formatting/refactoring in feature patches, and remove unused code rather than keeping an alternative implementation beside the active workflow.

Demo records are fictional. Initial seeding validates current field values and skips databases that already contain accounts or animals, so testing a restart does not recreate deliberately deleted records.
