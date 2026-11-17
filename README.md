# Tail Trails — Django/PostgreSQL prototype

Tail Trails is a role-based animal profile platform for shelters and rescues. This version uses Python 3.14, Django 5.2 LTS, PostgreSQL, and an ASGI/Uvicorn runtime, with model migrations, built-in authentication foundations, transactional approval workflows, structured uploads, an ordered animal photo gallery, and a read-only Server-Sent Events status stream.

## Run with Docker Compose

```bash
cp .env.example .env
# Replace SECRET_KEY and POSTGRES_PASSWORD in .env.
docker compose up --build
```

Open <http://localhost:8000> with the default `TAILTRAILS_PORT=8000`. On first startup, Django applies migrations and creates demonstration data.

If replacing an earlier prototype build, force Docker to discard the old application image while preserving the local database and upload folders:

```bash
docker compose down --remove-orphans
docker compose build --no-cache app cleanup
docker compose up -d --force-recreate
curl http://localhost:8000/healthz
```

The health response reports the value stored in the root `VERSION` file. If another version appears after an upgrade, the reverse proxy is still routing to an older container or the new project archive was not extracted into the Compose directory.

`VERSION` is the single authoritative build number used by Django, the health endpoint, static-asset cache keys, the administrator System Information page, release tags, and generated artifacts. Update only that file when starting a new iteration; Compose and `.env` do not duplicate or override it.

For repository setup, importing release ZIPs, branches, commits, tags, Git-based deployment, and generating ZIPs from tags, see [`GIT_WORKFLOW.md`](GIT_WORKFLOW.md).

All persistent data stays in folders beside `docker-compose.yml`; no named Docker volumes are used:

- `postgres-data/pgdata/` — PostgreSQL database cluster files. `PGDATA` deliberately points to this child directory so the bind-mount root may safely contain `.gitkeep`.
- `uploads/` — animal, submission, logo, and banner images

On Linux, the container defaults to UID/GID `1000:1000`. Change `TAILTRAILS_UID` and `TAILTRAILS_GID` in `.env` if the two persistent folders belong to a different local user.

## In-place upgrades

Release archives contain one top-level `tail-trails/` folder. Do not delete or replace the live folder wholesale because `.env`, uploaded files, and the PostgreSQL cluster live inside it. Preserve these paths during every upgrade:

- `.env`
- `uploads/`
- `postgres-data/`
- `data/` when SQLite development data is used
- `.git/` when the deployment directory is a repository

From the existing `tail-trails` directory, create backups while the current database is still running:

```bash
cd /path/to/tail-trails

docker compose exec -T db sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  > ../tailtrails-before-upgrade.sql

tar -czf ../tailtrails-uploads-before-upgrade.tar.gz uploads
cp .env ../tailtrails-env-before-upgrade
docker compose down
```

Extract the new archive into a temporary staging directory:

```bash
stage_dir=$(mktemp -d)
unzip /path/to/Tail_Trails_Django_PostgreSQL_Prototype.zip -d "$stage_dir"
```

Preview the application-file replacement. The excluded persistent paths must not appear as deletions:

```bash
rsync -avhn --delete \
  --exclude='.env' \
  --exclude='.git/' \
  --exclude='uploads/' \
  --exclude='postgres-data/' \
  --exclude='data/' \
  "$stage_dir/tail-trails/" ./
```

After reviewing the dry run, apply the same synchronization without `-n`:

```bash
rsync -avh --delete \
  --exclude='.env' \
  --exclude='.git/' \
  --exclude='uploads/' \
  --exclude='postgres-data/' \
  --exclude='data/' \
  "$stage_dir/tail-trails/" ./

docker compose config
docker compose build --no-cache app cleanup
docker compose up -d --force-recreate
docker compose ps
docker compose logs --tail=100 app
curl http://127.0.0.1:${TAILTRAILS_PORT:-8000}/healthz
```

Container startup applies database migrations automatically. Confirm the current shelter migrations with `docker compose exec app python manage.py showmigrations shelter`. Direct `unzip -o` extraction is not recommended because it can leave obsolete application files behind.

## Demo accounts

All demonstration accounts use password `Trail123!`.

| Role | Email |
| --- | --- |
| Administrator | `admin@tailtrails.test` |
| Employee | `employee@tailtrails.test` |
| Volunteer | `volunteer@tailtrails.test` |

## Photo gallery

Each animal has an ordered `AnimalPhoto` collection rather than a JSON photo list. Animal profiles provide:

- A main photograph with clickable thumbnails
- Visible previous/next controls on the public profile
- Full-screen viewing
- Previous/next buttons and keyboard-arrow navigation
- Accurate photo counts
- Staff upload, removal, and primary-cover selection controls
- Aggregate upload progress for all selected photos, with screen-reader announcements
- Per-photo original-file downloads for Employees and Administrators
- A maximum of five official photographs
- Approval-time replacement selection when volunteer photos would exceed the limit

Volunteer uploads are candidate photos rather than reserved gallery slots. Volunteers can track their own pending, approved, and rejected submissions, including photo previews and rejection reasons. Staff review displays both the submitted candidates and the current official gallery, can approve only a subset of candidates, and can select official photos to remove. Every approval locks and rechecks the animal's current gallery, so earlier approvals from other pending submissions cannot cause the five-photo limit to be exceeded.

Staff and volunteer photo uploads use a two-stage workflow. The complete multipart upload first stores private pending originals. Only after that upload succeeds does Tail Trails open the crop workspace for every uploaded image. The full image stays fixed at a practical display size while an independent 3×3 crop rectangle moves and resizes over it. Landscape and portrait controls change the locked selection ratio without resizing the displayed image. Finalization retains the exact source under `uploads/private-originals/` and creates an exact-ratio progressive JPG under the corresponding `web/` folder. Pending batches never appear publicly or consume official gallery positions.

Animal-photo inputs accept JPG, PNG, HEIC, and HEIF. HEIC/HEIF sources are decoded by `pillow-heif`, retained unchanged for authorized original-file downloads, and converted through the same optimized web-JPG pipeline as other formats. The server validates both the supported filename extension and the decoded image because some browsers label HEIC/HEIF uploads as generic binary data.

Each photo may be up to 25 MiB by default (`MAX_PHOTO_SIZE_MB`). The complete application request limit defaults to 160 MiB (`MAX_REQUEST_SIZE_MB`), which accommodates five maximum-sized photos plus multipart-form overhead. Any reverse proxy in front of the app must allow at least the same request size. The included Nginx example sets `client_max_body_size 160m`; confirm any Apache request-body policy also permits at least 160 MiB. Reload the active proxy after changing its configuration and rebuild the app with `docker compose up --build` after changing `.env`.

The configured width and height are treated as the long and short edges. With the defaults, landscape crops become 1600×1200 and portrait crops become 1200×1600. EXIF rotation is applied before cropping, and the image is never stretched. New uploads fill the configured aspect ratio through the administrator- or volunteer-selected crop, without letterboxing or blurred edge fill. Quality can be adjusted with `PHOTO_WEB_QUALITY`. Cards and public galleries use only the optimized JPG. The private source path is blocked from the public media route; authorized staff can download originals through the Django administration backend.

Crop batches default to a fixed 30-minute lifetime beginning after upload success (`PHOTO_BATCH_TTL_MINUTES`). The page displays a server-synchronized countdown in real time and supports resuming an unfinished batch from the animal editor or volunteer form. Cancelling deletes pending files immediately. Expired sessions are rejected at their exact deadline even if physical cleanup has not run yet. A dedicated `cleanup` Compose service runs every 60 minutes by default (`PHOTO_BATCH_CLEANUP_INTERVAL_MINUTES`), while application startup and new-batch creation also perform cleanup. The service shares the existing `uploads/` bind mount and PostgreSQL database; it exposes no port and uses no named Docker volume.

Container startup also runs `python manage.py reprocess_photos`. This one-time-safe backfill converts photos stored by earlier prototype versions, treating the preexisting file as the retained original.

To regenerate legacy web images from retained originals, run:

```bash
docker compose exec app python manage.py reprocess_photos --all
```

Only photos with retained originals are regenerated. This legacy maintenance command does not invent interactive crop coordinates; remote demonstration-image URLs are left unchanged.

Demonstration records use remote genuine-animal photographs, so seeded records have no local original unless a staff member replaces or adds a photo.

## Organization branding

Organization settings provides explicit format and size guidance, native file-picker restrictions, fixed-image crop previews, movable and aspect-locked 3×3 selections, and synchronized visual/hex color inputs. Logo and favicon selections remain square; the banner selection uses the configured banner ratio. The browser sends normalized crop coordinates; Pillow applies the authoritative crop to the retained original, so the browser preview never becomes the saved source.

All crop selectors use Pointer Events, so the same move and corner-resize interaction works with a mouse, pen, or touchscreen. The selection can also be moved with the arrow keys, moved faster with Shift+Arrow, and resized around its center with `+` and `-`. The crop cannot leave the image, and the server validates the target ratio again before generating the final asset.

Branding preview uploads and final image saves report byte progress. Selecting an image or changing a crop starts an image-editing countdown using `PHOTO_BATCH_TTL_MINUTES` (30 minutes by default). The server rejects expired image edits. Name/color-only edits do not start this timer. Preview uploads return decoded bytes without storing pending assets: discard or closing the page drops browser selections, and there are no abandoned preview files for the cleanup worker to delete. Existing saved branding stays in place until Save succeeds. Discard resets the image session and reloads saved settings.

Existing photos on the animal editor use bounded 4:3 management cards. The grid keeps a single photo at a practical thumbnail size instead of stretching it across the available row, while still fitting multiple photos efficiently and collapsing to one responsive column on narrow screens. Crop-session actions are separated from the final crop card with a consistent action gutter.

- Logos accept JPG or PNG, retain the source privately, and generate a 512 x 512 PNG. The square crop preserves transparency.
- Homepage banners accept JPG, PNG, HEIC, or HEIF, retain the source privately, and generate a progressive JPG. The default 1920 x 640 output is configurable with `BRANDING_BANNER_WIDTH`, `BRANDING_BANNER_HEIGHT`, and `BRANDING_WEB_QUALITY`.
- Favicons accept JPG or PNG and use the same square crop interface. Optimized 32 x 32 and 180 x 180 PNG variants use content-derived filenames so browsers receive a fresh URL whenever branding changes.
- Branding sources default to a 25 MiB limit controlled by `BRANDING_MAX_SIZE_MB`.

The public homepage displays the generated banner beneath a dark readability overlay. If no dedicated favicon is uploaded, the processed logo is used; if neither image exists, Tail Trails generates a high-contrast heart using the primary organization color. HEIC/HEIF crop previews are decoded by an administrator-only Django endpoint because browser support for those formats is inconsistent. Existing branding files are retained as source references during the database migration and can be replaced or recropped through Organization settings.

The sign-in page presents the prototype password in monospace for easier transcription. Photo forms preserve aggregate upload progress after a server-side validation response, so correcting an over-capacity selection and submitting again does not require a page refresh.

## Administrator system information

Administrators have a **System information** page in the Administration navigation. It provides a request-time operational snapshot containing:

- The build number from `VERSION`, Python version, Django version, and configured time zone
- Database connectivity, response time, engine, and most recently applied migration
- The configured upload-data path and its total, used, and free filesystem capacity
- Web-image dimensions, JPEG quality, per-file limit, request limit, and gallery capacity
- Container-visible operating system, CPU model, logical CPUs, 1/5/15-minute load averages, kernel uptime, process ID, process resident memory, RAM use, and swap use

Storage and memory quantities use IEC binary units (`KiB`, `MiB`, `GiB`, `TiB`, and `PiB`) so labels match their 1024-based calculations.

The browser opens an authenticated Server-Sent Events connection and replaces only the snapshot cards when fresh data arrives; it does not reload the page. Administrators can select a 1-, 2-, or 5-second update frequency from the page header, with 5 seconds as the default. The selected interval is retained in the page URL. The stream pauses while the tab is hidden, reconnects automatically after interruptions, and falls back to a static snapshot when JavaScript is unavailable.

The page is restricted to Administrators. It does not display secrets, database passwords, environment values, or uploaded-file contents. RAM and swap prefer cgroup values when numeric container limits are available and otherwise fall back to kernel-visible `/proc` values. Disabled or unavailable swap is identified explicitly. Server usage figures are snapshots from the application container and may represent container limits or host-kernel values depending on the deployment.

## Reverse proxy

The app trusts one proxy layer for scheme and host information and continues to recognize `X-Forwarded-Prefix` for custom deployments. The included `nginx.example.conf` and `apache.example.conf` instead demonstrate the simpler recommended layout: publish Tail Trails at the root of the dedicated HTTPS subdomain `tailtrails.exampleshelter.com`. Both examples redirect HTTP to HTTPS, use the same Let's Encrypt certificate paths, preserve the original host, set HSTS at the proxy, and forward to the loopback-only application port. Replace the example domain and certificate paths before deployment.

Compose publishes the Uvicorn ASGI service only on the host loopback interfaces: `127.0.0.1:${TAILTRAILS_PORT}:8000` and `[::1]:${TAILTRAILS_PORT}:8000`. The host-side port remains configurable through `TAILTRAILS_PORT` in `.env`, while remote hosts cannot connect directly to Uvicorn. A reverse proxy running on the same host should use `http://127.0.0.1:${TAILTRAILS_PORT}` as its upstream. A reverse proxy running in another container cannot use the host loopback mapping; attach it to the Compose network and use `http://app:8000` instead. The SSE response disables buffering and both examples allow a 600-second upstream timeout.

For the example subdomain, configure `.env` with `TRUSTED_HOSTS=tailtrails.exampleshelter.com`, `CSRF_TRUSTED_ORIGINS=https://tailtrails.exampleshelter.com`, and `COOKIE_SECURE=true`. Apache deployments require the SSL, headers, rewrite, proxy, proxy HTTP, and HTTP/2 modules used by `apache.example.conf`.

For HTTPS deployment:

1. Set `TRUSTED_HOSTS=shelter.example.org`.
2. Set `CSRF_TRUSTED_ORIGINS=https://shelter.example.org`.
3. Set `COOKIE_SECURE=true` so browsers never transmit session and CSRF cookies over plain HTTP.
4. Configure HTTP-to-HTTPS redirection and the HSTS response header at the reverse proxy. The Django application leaves both disabled by default to avoid duplicating proxy policy.
5. Ensure the proxy sends `X-Forwarded-Proto`; Django uses it to recognize the original request as HTTPS.
6. Use a strong, unique `SECRET_KEY` and database password.
7. Keep PostgreSQL unexposed; only the application service needs to reach it.

## Permanent deceased status and record archives

Employees and administrators select **Deceased** in the animal's status dropdown when creating or editing a profile. Selecting it reveals a required reason, a permanent-change acknowledgement, and the signed-in user's current-password field. Saving requires all three, records the reason, confirming user and timestamp, and adds a history entry. Once confirmed, the status, reason and confirmation details cannot be changed through model saves or database updates; PostgreSQL and SQLite triggers protect them. Other profile details can still be maintained. Django administration directs users to the application form for this confirmation.

Migration 0009 converts existing Euthanized records to Deceased without losing their confirmation timestamps or users. Those legacy records receive the reason "Previously recorded as euthanized." New confirmations require a reason supplied by staff. New-profile creation supports records with or without photos; photo uploads continue into the crop workflow after the record saves. Invalid forms display a prominent linked error summary and retain entered values, so validation failures cannot look like a successful save.

Archiving is separate and reversible: toggle **Is archived** on the edit page and save. Archived animals disappear from normal searches, homepage features, and public profiles even if their adoption status is Available. Employees and administrators can tick **Include archived records** in animal search, open an archived record, and restore it by clearing the archive checkbox. Sorting preserves the archive filter. Volunteers cannot browse archived profiles or start new submissions for them; existing submission history remains available for review and audit. Restoring an archive never reverses a confirmed deceased status. Records created before archiving was introduced default to unarchived; existing confirmations are preserved.

## Structured animal intake and care fields

The status and archive controls share a stable row; the conditional Deceased confirmation appears below that row. All conditional rules are enforced on the server as well as in the browser.

| Selection | Form behavior |
| --- | --- |
| Intake type: Stray | Intake location appears and is required. It is hidden and disabled for other intake types. Found by is removed from the form. |
| Intake type: Owner Surrender | Show Previous owner immediately after Intake type; hide it otherwise. |
| Held at: Kennel | Show and require Kennel location and Kennel ID. |
| Held at: Foster Home | Show and require foster phone and address; caregiver name remains optional. Contact details appear only in restricted staff records. |
| Has Microchip | Checkbox and ID share one panel. Enable and require the ID when checked; otherwise visibly grey and disable it and clear the saved ID. |
| Spay/neuter: Nursing | Show and require both litter size and litter date of birth. |
| Species: Dog or Cat | Show optional leash skills. Hide and disable it for other species. |

Intake options are Stray, Owner Surrender, Animal Control, Transfer, Seizure and Other. Age units are Weeks, Months and Years; age sorting compares normalized durations. Spay/neuter choices are Spayed/Neutered, Not Spayed/Neutered, Unknown and Nursing. Vaccination status offers Up to Date, In Progress and Unvaccinated, with optional notes and a blank initial choice. Heartworm offers Positive, Negative and Unknown, initially blank; fleas offers Positive and Negative, initially blank. House trained and leash skills offer Yes, No and Unknown, initially blank. Coat length is Short, Medium or Long, initially blank. Weight is in kg to three decimal places (grams), and height in cm to one decimal place (millimeters).

Breed and coat-pattern suggestions appear immediately with a live matching/total count. Search filters the chips. When no suggestion matches, an explicit empty-state message and an **Add** button let staff select their typed custom value. Multiple values can be selected and removed. Breed pools contain 30 suggestions per species for dogs and cats; rabbit/other breeds can be entered directly. These are practical intake suggestions, not an authoritative population ranking or breed identification. Reference pools: [AKC popular breeds](https://www.akc.org/most-popular-breeds/) and [CFA popular pedigreed breeds](https://cfa.org/cat-talk/most-popular-breeds-for-2024/), supplemented with domestic coat-length types and mixed breeds. Coat-color checkboxes are Black, White, Blue/Gray, Red/Orange, Tan, Cream, Brown and Silver. Multiple colors can be searched individually; no selection means not recorded, without Unknown or Other checkboxes.

Migration 0010 maps prior spay/neuter terms, marks existing microchip IDs as present, and separates known legacy patterns from colors. It preserves ambiguous prior medical/behavior values in vaccination notes or staff notes rather than treating old “Vaccinated” text as proof of current vaccination. Existing foster records are not assigned fabricated contact details; required missing information must be supplied on their next edit. Retired energy-level, spay-note and flea-prevention columns are retained for data preservation but removed from forms and profile displays. Permanent Deceased confirmation data stays protected through the migration. Demo seeding now creates missing records only and never overwrites staff edits or archived/permanent statuses.

Migration 0011 merges Blue/Gray and Red/Orange aliases and preserves retired color names in staff notes. Legacy weights are converted from pounds to kg, and size classifications use the metric values. Old heights had no defined unit: their original values are preserved in staff notes and the cm field is cleared for verification rather than assigning an assumed unit. Permanent confirmation data remains protected. Disabled controls use an explicit gray background and readable gray text.

## Local development and tests

PostgreSQL is used in Compose. Tests can use an isolated SQLite database for speed:

```bash
python3.14 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
DB_ENGINE=sqlite python manage.py migrate
DB_ENGINE=sqlite python manage.py seed_demo
DB_ENGINE=sqlite python manage.py runserver
```

Run the automated tests:

```bash
DB_ENGINE=sqlite python manage.py test
```

The tests cover public visibility, role boundaries, gallery rendering, two-stage multi-image cropping, fixed-image 3×3 crop selectors, exact-ratio output, resumable deadlines, cancellation, expired-file cleanup, volunteer approval, branding crops and retained originals, HEIC previews, color controls, upload retries, CPU/swap diagnostics, the administrator SSE stream, ASGI configuration, dependency policy, loopback-only port publishing, reverse-proxy examples and prefixes, and health checks.

## Dependency update policy

`requirements.in` defines the supported feature series for direct dependencies. `requirements.lock` records the exact transitive dependency set and distribution hashes used by Docker and local testing. Docker never resolves newer packages implicitly, so rebuilding a tagged release remains reproducible.

At the start of a new Tail Trails release, install [uv](https://docs.astral.sh/uv/) and intentionally refresh the lock file:

```bash
uv pip compile requirements.in \
  --python-version 3.14 \
  --universal \
  --generate-hashes \
  --output-file requirements.lock

python3.14 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
DB_ENGINE=sqlite python manage.py test
```

Review the resolved versions and test results before committing the new lock file. The Docker base image is likewise pinned to an exact Python 3.14 patch release and should be advanced deliberately during release preparation rather than changing silently during an ordinary rebuild.

## Production follow-up

Before operating with real shelter data, add automated PostgreSQL and upload backups, malware scanning for uploads, centralized logging, rate limiting, monitoring, email-based password recovery, and object storage if the application will run on more than one server.
