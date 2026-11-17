# Tail Trails prototype

Tail Trails is a role-based animal profile platform for shelters and rescues, built with Python 3.14, Django 5.2 LTS, PostgreSQL and Uvicorn/ASGI. The frontend uses Django templates, CSS and vanilla JavaScript.

Database tables and permanent deceased-status safeguards are created by the initial Django schema in `shelter/migrations/0001_initial.py`.

## Install with Docker Compose

Extract the release into a new directory, then:

```bash
cd /path/to/tail-trails
cp .env.example .env
# Set unique SECRET_KEY and POSTGRES_PASSWORD values in .env.
# Configure hostname/proxy settings for your deployment.
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 app
curl http://127.0.0.1:8000/healthz
```

The default `TAILTRAILS_PORT` is 8000. The health response reports the build number from `VERSION`. Startup applies the Django schema, removes expired pending uploads, seeds the demo database when empty and starts Uvicorn. Restarting the application keeps stored records and uploads; demo seeding skips databases that already contain accounts or animals.

Windows PowerShell commands for repository setup, ZIP extraction, release tags and deployment are provided alongside Linux/macOS shell commands in `GIT_WORKFLOW.md`.

All persistence uses bind-mounted folders next to `docker-compose.yml`; there are no named Docker volumes:

| Host folder | Purpose |
| --- | --- |
| `postgres-data/pgdata/` | PostgreSQL cluster; a child directory avoids initialization errors from mount-root metadata |
| `uploads/` | Private source images, pending uploads and generated web assets |
| `data/` | Optional SQLite database for local development |

On Linux, set `TAILTRAILS_UID` and `TAILTRAILS_GID` to match the local folder owner when it differs from `1000:1000`.

## Demo accounts

All demo accounts use password `Trail123!`:

| Role | Email |
| --- | --- |
| Administrator | `admin@tailtrails.test` |
| Employee | `employee@tailtrails.test` |
| Volunteer | `volunteer@tailtrails.test` |

Demo animals use current choices, metric values and complete required medical fields. Their remote example photos have no retained local originals. Secure or replace demonstration accounts before real use. A Django backend superuser can be created separately with `docker compose exec app python manage.py createsuperuser`.

## Roles and animal records

Public visitors can search available, non-archived profiles and browse galleries. Volunteers submit observations and candidate photos for staff review and track their own submissions. Employees and Administrators maintain official records and volunteer activities. Administrators additionally manage users, branding, total-hour adjustments, system information and permanent animal deletion.

Animal forms enforce these rules in both the browser and server:

| Field/selection | Behavior |
| --- | --- |
| Stray intake | Show and require Intake location |
| Owner Surrender intake | Show Previous owner |
| Kennel | Require Kennel location and Kennel ID |
| Foster Home | Require foster phone and address; caregiver name is optional |
| Has Microchip | Require the ID when checked; otherwise gray/disable only the ID area |
| Nursing | Require litter size and date of birth |
| Dog or Cat | Show optional Yes/No/Unknown leash skills |
| Fleas | Required Positive/Negative selection; initially blank |
| Heartworm | Required Positive/Negative/Unknown selection; initially blank |

Intake types are Stray, Owner Surrender, Animal Control, Transfer, Seizure and Other. Spay/neuter choices are Spayed/Neutered, Not Spayed/Neutered, Nursing and Unknown. Vaccination status offers Up to Date/In Progress/Unvaccinated or blank, plus notes. House trained offers Yes/No/Unknown or blank. Breed and coat pattern support multiple suggestion chips and custom values, with counts and an explicit no-match state. Color checkboxes are Black, White, Blue/Gray, Red/Orange, Tan, Cream, Brown and Silver. Coat length is Short/Medium/Long or blank.

Age uses Weeks/Months/Years with one decimal place. Weight is kg to 0.001 and height is cm to 0.1. Unsigned text controls reject negative typing/pastes without scroll-wheel increments; server validation also rejects negative submissions. Age, measurements and entered Total Hours permit zero. Nursing litter size must be at least 1; an activity must be at least 0.01 hours. The stored manual hour adjustment remains signed to support downward total corrections.

## Deceased status, archive and deletion

Employees and Administrators select **Deceased** in the normal status dropdown. Saving requires a reason, an acknowledgement checkbox and the signed-in user's current password. The reason, actor and time are retained on the animal. Model checks and PostgreSQL/SQLite triggers prevent reversing that confirmation, while other details remain editable. Django's backend does not offer a bypass for confirming or reversing this status.

**Archive this record** is reversible and separate from status. Archived animals disappear from normal searches, homepage features and public pages. Staff can tick **Include archived records**, open the record and restore it. Volunteers cannot start contributions to archived records; their existing submission outcomes remain accessible.

Only Administrators see the distinct red **Delete animal record…** action next to Cancel/Save. A second page requires acknowledgement and password. Deletion removes the animal, submissions, gallery associations and pending batches in a transaction, then removes unshared image files after commit. Files referenced elsewhere are preserved. Direct Django backend deletion is disabled. Use Archive when the record should be retained. A permanent deceased status cannot be reversed, but an Administrator can deliberately delete the whole record through this protected workflow.

## Animal photos and cropping

Official galleries allow five photos, primary-cover selection, clickable thumbnails, previous/next controls and a large-image view with keyboard navigation. Image management cards use bounded 4:3 thumbnails; missing files show styled placeholders.

Animal uploads accept JPG, PNG, HEIC and HEIF, with extension and decoded-content validation. A complete multipart upload succeeds before opening cropping for every uploaded image. A fixed, uniformly scaled preview has a movable/resizable 3×3 crop selection, locked to the selected landscape/portrait ratio. Mouse, pen, touch and keyboard controls are supported. Finalization retains the exact original filename/bytes privately and creates a progressive web JPG without letterboxing.

Defaults are 1600×1200 landscape / 1200×1600 portrait, 25 MiB per file and 160 MiB per complete request. The configured width/height are treated as long/short edges. EXIF rotation is applied before cropping. Employees and Administrators can download each retained original from the animal editor; public media access blocks private original paths.

File selection reports count/combined size. Save shows aggregate byte progress, then processing status. Corrected retries retain progress behavior. Selection is disabled at five official photos; selecting too many files before reaching five still produces a server validation error.

A crop batch lasts 30 minutes by default and displays a server-synchronized countdown. Cancellation removes pending files immediately; expiration rejects finalization at the deadline even before physical cleanup. Startup, opportunistic new-batch checks and a cleanup service remove expired batches. `PHOTO_BATCH_CLEANUP_INTERVAL_MINUTES` defaults to 60. To clean expired batches immediately:

```bash
docker compose exec app python manage.py cleanup_photo_batches
```

## Volunteer submissions and hours

Candidate photos do not reserve official gallery slots. Volunteers can submit up to five candidates and see Pending/Approved/Rejected outcomes, previews and rejection reasons in **My submissions**. Staff review displays candidates beside current official photos. Reviewers choose candidates to add and official photos to replace. Approval locks/rechecks the current animal gallery inside a transaction, preventing multiple submissions from exceeding five official photos.

**Displayed Total Hours = recorded activity sum + manual adjustment.** Administrators replace Total Hours in **Manage users → Edit**; the adjustment becomes entered total minus recorded sum. Activity entries remain unchanged. Employees and Administrators can add/edit/delete activities; deletion has a separate acknowledgement page. Later activity changes preserve the adjustment. Consequently, deleting activities after a downward adjustment can yield a negative calculated total; the system does not silently rewrite the adjustment or clamp the calculation.

Changing Volunteer to Employee/Administrator preserves entries and adjustment but hides Volunteer Hours for that account. Restoring Volunteer reveals the preserved total. Total replacement is enabled only for Volunteer accounts.

## Organization branding

Branding uses synchronized color pickers/hex values and the shared fixed-image crop selector. Logo and favicon require square crops; banner uses its configured ratio. Non-square sources are uniformly scaled, never squished.

| Asset | Accepted formats | Output |
| --- | --- | --- |
| Logo | JPG/PNG | 512×512 PNG with transparency |
| Banner | JPG/PNG/HEIC/HEIF | 1920×640 progressive JPG by default |
| Favicon | JPG/PNG | 32×32 and 180×180 PNG variants |

Preview/final uploads show progress. Image changes start the configured crop-session timer; name/color-only edits do not. Preview responses create no stored pending assets. Discard drops browser selections; saved settings change only after Save succeeds. Originals are retained privately when saved. Browser-icon fallback is dedicated favicon, then logo, then a color-matched heart. Generated filenames change with branding content. The homepage banner has a dark overlay for text readability.

## Environment and reverse proxy

See `.env.example` for the complete supported configuration. Important controls include:

| Variables | Purpose |
| --- | --- |
| `TAILTRAILS_PORT`, `TAILTRAILS_UID`, `TAILTRAILS_GID` | Host port and local folder ownership |
| `PHOTO_WEB_WIDTH`, `PHOTO_WEB_HEIGHT`, `PHOTO_WEB_QUALITY` | Animal web output |
| `MAX_PHOTO_SIZE_MB`, `MAX_REQUEST_SIZE_MB` | Per-file and complete request size |
| `PHOTO_BATCH_TTL_MINUTES`, `PHOTO_BATCH_CLEANUP_INTERVAL_MINUTES` | Crop lifetime and expired-file cleanup |
| `BRANDING_LOGO_SIZE`, `BRANDING_BANNER_WIDTH`, `BRANDING_BANNER_HEIGHT` | Branding output dimensions |
| `BRANDING_WEB_QUALITY`, `BRANDING_MAX_SIZE_MB` | Branding JPG quality and upload size |

Compose exposes only `127.0.0.1:${TAILTRAILS_PORT}:8000` and `[::1]:${TAILTRAILS_PORT}:8000`. PostgreSQL is not published. Apache and Nginx examples host the root of a dedicated HTTPS subdomain, redirect HTTP to HTTPS and set HSTS at the proxy. Replace the example hostname/certificate paths. Set `TRUSTED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and `COOKIE_SECURE=true` for HTTPS deployment. The proxy must preserve host and `X-Forwarded-Proto`, allow the 160 MiB request default, disable SSE buffering and permit the configured long upstream timeout.

A same-host proxy uses the loopback port. A containerized proxy should share the Compose network and use `http://app:8000`. Django leaves HTTPS redirect/HSTS disabled by default to avoid duplicating proxy policy. Optional custom URL-prefix support remains available for deployments that need it.

## Administrator system information

The read-only page reports build/runtime versions, timezone, database health/latency/schema, upload folder capacity, image settings, CPU model/count/load, uptime, process memory, RAM and swap. Capacity uses IEC units such as GiB and TiB. Values are container-visible and may reflect host-kernel or cgroup limits.

Authenticated Server-Sent Events replace snapshot cards without a full reload. The refresh menu offers 1/2/5 seconds, default 5, retained in the URL. It pauses in hidden tabs, reconnects after interruption and has a static fallback without JavaScript. Secrets and uploaded contents are excluded.

## Development and collaboration

See `CONTRIBUTING.md` for project structure and contribution checks, and `GIT_WORKFLOW.md` for ZIP imports, branches, tags and deployment. `VERSION` is the single application build number used by health/UI/cache keys and the PDF generator.

For a new local development database:

```bash
python3.14 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
DB_ENGINE=sqlite python manage.py migrate --noinput
DB_ENGINE=sqlite python manage.py seed_demo
DB_ENGINE=sqlite python manage.py runserver
```

Checks:

```bash
DB_ENGINE=sqlite python manage.py test
DB_ENGINE=sqlite python manage.py makemigrations --check --dry-run
node tests/test_unsigned_inputs.js  # Optional; requires Node.js
```

`requirements.in` defines compatible dependency series; `requirements.lock` pins exact versions/hashes. Refresh compatible patches deliberately, review and rerun tests before a release. The Docker Python base is also pinned for reproducibility. `tools/build_overview.py` optionally builds the overview using ReportLab, which is not an application dependency:

```bash
python -m pip install reportlab
python tools/build_overview.py --output /path/to/Tail_Trails_Architecture_Overview.pdf
```

Review its narrative for each release and pass `--verified-tests N` only after actually running that release's tests.

For real shelter deployment, add automated PostgreSQL/upload backups, malware scanning, rate limiting, monitoring, account recovery and shared object storage if multiple application hosts are introduced.
