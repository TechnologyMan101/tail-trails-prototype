"""Optional PDF builder: python -m pip install reportlab; python tools/build_overview.py.
The running application does not require ReportLab. VERSION is the release source.
"""

import argparse
import re
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Preformatted,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text().strip()
lock = (ROOT / "requirements.lock").read_text()
DJANGO = re.search(r"^django==([^\s]+)", lock, re.M).group(1)
PYTHON = re.search(r"FROM python:([^\s-]+)", (ROOT / "Dockerfile").read_text()).group(1)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--output", type=Path, default=ROOT / "docs/Tail_Trails_Architecture_Overview.pdf"
)
parser.add_argument(
    "--verified-tests",
    type=int,
    help="Number of tests actually passed for this release.",
)
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
GREEN = colors.HexColor("#245C4A")
DARK = colors.HexColor("#173D32")
INK = colors.HexColor("#183129")
MUTED = colors.HexColor("#60756D")
PALE = colors.HexColor("#EDF4F0")
LINE = colors.HexColor("#D7E2DD")
base = getSampleStyleSheet()
styles = {
    "title": ParagraphStyle(
        "title",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=31,
        leading=37,
        textColor=colors.white,
        spaceAfter=18,
    ),
    "sub": ParagraphStyle(
        "sub",
        parent=base["BodyText"],
        fontSize=12,
        leading=18,
        textColor=colors.HexColor("#DFEDE5"),
    ),
    "h1": ParagraphStyle(
        "h1",
        parent=base["Heading1"],
        fontSize=21,
        leading=25,
        textColor=DARK,
        spaceAfter=13,
    ),
    "h2": ParagraphStyle(
        "h2",
        parent=base["Heading2"],
        fontSize=12.5,
        leading=16,
        textColor=GREEN,
        spaceBefore=11,
        spaceAfter=6,
    ),
    "body": ParagraphStyle(
        "body",
        parent=base["BodyText"],
        fontSize=9,
        leading=13.5,
        textColor=INK,
        spaceAfter=7,
    ),
    "note": ParagraphStyle(
        "note",
        parent=base["BodyText"],
        fontSize=9,
        leading=13.5,
        textColor=DARK,
        backColor=PALE,
        borderPadding=10,
        spaceBefore=5,
        spaceAfter=14,
    ),
    "small": ParagraphStyle(
        "small",
        parent=base["BodyText"],
        fontSize=8,
        leading=11,
        textColor=MUTED,
        spaceAfter=6,
    ),
    "th": ParagraphStyle(
        "th",
        parent=base["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.white,
    ),
    "td": ParagraphStyle(
        "td", parent=base["BodyText"], fontSize=8, leading=11, textColor=INK
    ),
    "code": ParagraphStyle(
        "code",
        parent=base["Code"],
        fontSize=7.7,
        leading=10.5,
        textColor=INK,
        backColor=PALE,
        borderPadding=8,
        spaceBefore=7,
        spaceAfter=10,
    ),
}
# Embed bundled TrueType fonts so PDF readers do not substitute Type 1 fonts.
font_root = Path(reportlab.__file__).parent / "fonts"
for name, filename in [("OverviewSans", "Vera.ttf"), ("OverviewBold", "VeraBd.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(font_root / filename)))
pdfmetrics.registerFontFamily(
    "OverviewSans",
    normal="OverviewSans",
    bold="OverviewBold",
    italic="OverviewSans",
    boldItalic="OverviewBold",
)
for style in styles.values():
    style.fontName = (
        "OverviewSans"
        if style.fontName == "Courier"
        else ("OverviewBold" if style.fontName.endswith("Bold") else "OverviewSans")
    )
story = []


def p(text, style="body"):
    return Paragraph(text, styles[style])


def para(text, style="body"):
    story.append(p(text, style))


def head(text):
    para(text, "h2")


def bullets(items):
    for item in items:
        para("&#8226; " + item)


def table(rows, widths):
    t = Table(
        [
            [p(str(c), "th" if i == 0 else "td") for c in row]
            for i, row in enumerate(rows)
        ],
        colWidths=[w * inch for w in widths],
        repeatRows=1,
        hAlign="LEFT",
    )
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F7FAF8")],
                ),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(t)


def code(text):
    story.append(Preformatted(text, styles["code"]))


def page(title):
    story.append(PageBreak())
    para(title, "h1")


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(47, 42, 565, 42)
    canvas.setFillColor(MUTED)
    canvas.setFont("OverviewSans", 7.5)
    canvas.drawString(47, 28, f"Tail Trails Prototype | Build {VERSION}")
    canvas.drawRightString(565, 28, f"{doc.page}")
    canvas.restoreState()


# 1
story.append(Spacer(1, 24))
cover = Table(
    [
        [p("TAIL TRAILS PROTOTYPE", "sub")],
        [p("Architecture and<br/>Structure Overview", "title")],
        [
            p(
                "Django, PostgreSQL, role-based animal records,<br/>and a configurable photo pipeline.",
                "sub",
            )
        ],
    ],
    colWidths=[7.1 * inch],
)
cover.setStyle(
    TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, -1), DARK),
            ("LEFTPADDING", (0, 0), (-1, -1), 26),
            ("RIGHTPADDING", (0, 0), (-1, -1), 26),
            ("TOPPADDING", (0, 0), (-1, -1), 20),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ]
    )
)
story.append(cover)
story.append(Spacer(1, 23))
para(f"BUILD {VERSION}", "h2")
para(
    "Prepared for maintainers, reviewers and deployment owners. This document describes the packaged implementation and its current project scope."
)
head("Changes in this build")
bullets(
    [
        "Fresh-install-only baseline with one initial Django schema and no historical upgrade chain.",
        "Retired animal columns, obsolete status URLs, unused crop/dialog code and blurred-letterbox conversion are removed.",
        "The single active photo pipeline crops every uploaded image while retaining its original. Current-format demo data needs no historical conversions.",
        "Startup refuses earlier/untracked schemas without modifying data. Restarts keep this baseline's records without recreating deliberately deleted demo animals.",
        "README, Git workflow and CONTRIBUTING.md describe the clean installation and collaboration base.",
    ]
)
para(
    "The VERSION file supplies the build number to the application and this PDF generator. The optional generator is included under tools/ for future releases.",
    "small",
)

# 2
page("1. Architecture and technology")
para(
    "Tail Trails supports small and medium-sized shelters and rescues with animal intake, searchable adoption profiles, staff-controlled editing, volunteer proposals, hours management and organization branding."
)
para(
    "Browser HTTPS requests pass through Apache or Nginx to Django running under Uvicorn. PostgreSQL stores structured records. Local bind-mounted folders retain database files and uploaded originals/web images.",
    "note",
)
table(
    [
        ["Layer", "Technology", "Responsibility"],
        [
            "Language",
            f"Python {PYTHON}",
            "Application workflows, validation and image processing",
        ],
        [
            "Framework",
            f"Django {DJANGO} LTS",
            "Authentication, permissions, forms, templates, ORM and migrations",
        ],
        [
            "Database",
            "PostgreSQL 17",
            "Animals, users, photos, proposals, reviews and volunteer hours",
        ],
        [
            "Application server",
            "Uvicorn / ASGI",
            "HTTP handling and read-only Server-Sent Events",
        ],
        [
            "Frontend",
            "HTML, CSS, vanilla JavaScript",
            "Responsive forms, galleries, crops, uploads and live system snapshots",
        ],
        [
            "Images",
            "Pillow + pillow-heif",
            "JPG/PNG/HEIC decoding, orientation and optimized web variants",
        ],
        [
            "Deployment",
            "Docker Compose",
            "Application, PostgreSQL and pending-upload cleanup services",
        ],
    ],
    [1.15, 1.75, 4.2],
)
head("Request lifecycle")
bullets(
    [
        "The reverse proxy terminates HTTPS, enforces its redirect/HSTS policy, and forwards the original host and scheme.",
        "Django authenticates the session and checks the application role before exposing staff or administrator actions.",
        "Forms validate required fields, conditional values, number ranges, photos and confirmation passwords. Transactions and row locks protect gallery approval and permanent changes.",
        "Templates render HTML. WhiteNoise serves static CSS/JavaScript with build-based cache keys. Uploads use aggregate byte progress before image processing/cropping.",
    ]
)
head("Dependency policy")
para(
    "requirements.in defines compatible dependency series. requirements.lock pins exact direct/transitive versions and hashes. Docker installs the lock rather than silently resolving newer packages. Release preparation intentionally refreshes allowed patches, reviews the result and reruns verification. The Python base image is also pinned to an exact patch."
)

# 3
page("2. Source structure and authorization")
code("""tail-trails/
  config/                 Settings, root URLs, ASGI and WSGI
  shelter/
    models.py             Domain entities and permanent-status rules
    forms.py              Server validation and unsigned number inputs
    views.py              Roles, workflows, downloads and SSE
    photo_batches.py      Pending uploads, deadlines and finalization
    images.py             Animal originals and web-JPG generation
    branding_images.py    Branding previews, crops and variants
    diagnostics.py        Read-only system snapshots
    migrations/           One initial fresh-install schema
    management/commands/  Initialization, demo seed and pending cleanup
  templates/              Server-rendered pages
  static/                 CSS, JavaScript and fallback favicon
  tests/                  Django and optional JavaScript checks
  tools/build_overview.py Optional PDF generator
  Dockerfile, docker-compose.yml, VERSION
  README.md, GIT_WORKFLOW.md, CONTRIBUTING.md
  requirements.in, requirements.lock
  apache.example.conf, nginx.example.conf""")
table(
    [
        ["Role", "Capabilities"],
        [
            "Public",
            "View/search available, non-archived adoption profiles and photo galleries.",
        ],
        [
            "Volunteer",
            "View accessible profiles, submit observations/photos for review, track own submission outcomes, and see own accumulated hours.",
        ],
        [
            "Employee",
            "Create/edit/archive profiles, confirm Deceased, manage official photos/download originals, review submissions, and manage volunteer activities.",
        ],
        [
            "Administrator",
            "Employee capabilities plus users, Total Hours replacement, branding, system information and password-confirmed animal deletion.",
        ],
    ],
    [1.25, 5.85],
)
para(
    "Django superusers bypass application role checks. Private original paths are blocked from public media serving; Employees and Administrators use protected original-file download endpoints. Staff contact details and restricted notes are not exposed on public profiles.",
    "small",
)
head("Primary entities")
para(
    "User, Organization and Animal supply identity, branding and records. AnimalPhoto stores the ordered official gallery. Submission and SubmissionPhoto store volunteer proposals. PhotoUploadBatch and PendingPhoto support temporary cropping. VolunteerHour stores individual activities; User.manual_adjustment supplies the total offset."
)

# 4
page("3. Animal records and validation")
para(
    "Employees and Administrators maintain animal records. Conditional controls and required values are enforced on the server as well as in the browser. Invalid saves retain entered values and display a linked error summary."
)
table(
    [
        ["Field / selection", "Rule"],
        [
            "Fleas / Heartworm",
            "Required and initially blank. Fleas: Positive/Negative. Heartworm: Positive/Negative/Unknown. Staff explicitly choose each result before saving.",
        ],
        [
            "Intake type",
            "Stray, Owner Surrender, Animal Control, Transfer, Seizure or Other. Stray requires intake location. Owner Surrender reveals previous owner.",
        ],
        [
            "Held at",
            "Kennel requires location and ID. Foster Home requires phone and address; caregiver name is optional. Contact details remain restricted.",
        ],
        [
            "Has Microchip",
            "Checkbox and ID share a panel. Only the ID area is gray/disabled when unchecked. A checked box requires an ID.",
        ],
        [
            "Spay/neuter",
            "Spayed/Neutered, Not Spayed/Neutered, Nursing, Unknown. Nursing requires litter size and date of birth.",
        ],
        [
            "Coat / breed",
            "Multiple breed/pattern suggestion chips with custom values, match counts and empty states. Eight coat-color checkboxes. Coat length: Short/Medium/Long or blank.",
        ],
        [
            "Other medical / behavior",
            "Vaccination: Up to Date/In Progress/Unvaccinated or blank, plus notes. House trained: Yes/No/Unknown or blank. Leash skills use the same choices for Dog/Cat only.",
        ],
    ],
    [1.35, 5.75],
)
head("Quantity inputs")
para(
    "Age supports Weeks, Months and Years with one decimal place. Weight uses kg to 0.001; height uses cm to 0.1. These quantities and entered Total Hours permit zero. Nursing litter size must be at least 1; activity entries must be at least 0.01 hours. Unsigned text controls prevent wheel increments, reject invalid typing/pastes and provide numeric keyboard hints. Server validation remains authoritative."
)
head("Permanent status, archive and deletion")
bullets(
    [
        "Selecting Deceased reveals a required reason, acknowledgement and current-password field. Actor, time and reason stay on the animal. Model checks and database triggers prevent reversing the confirmation.",
        "Archive is separate and reversible. It hides records from normal search and public pages; staff can include archived records and restore them.",
        "Only Administrators see the distinct red Delete animal record action. A secondary page requires a checkbox and password. Deletion removes related submissions, pending batches and photo associations transactionally; unshared files are removed after commit.",
    ]
)

# 5
page("4. Animal photos and branding")
para(
    "Public cards and profiles use optimized assets. Original files remain available for authorized backend purposes with their original download filenames. Each official gallery allows five photos, with cover selection, thumbnails, previous/next controls and a keyboard-accessible large-image view."
)
table(
    [
        ["Control", "Default / behavior"],
        [
            "Animal photo formats",
            "JPG, PNG, HEIC and HEIF. Validate both extension and decoded content.",
        ],
        [
            "Per-file / request size",
            "25 MiB per photo; 160 MiB complete request to allow five files plus overhead. The reverse proxy must permit the same request size.",
        ],
        [
            "Web output",
            "Progressive JPG. Configured long/short edges default to 1600 x 1200 landscape or 1200 x 1600 portrait. EXIF orientation is applied first.",
        ],
        [
            "Cropping",
            "Upload must succeed first. Every uploaded photo gets a fixed-size image preview with an independent movable/resizable 3 x 3 crop rectangle. Ratio locks follow orientation. Mouse, touch, pen and keyboard are supported.",
        ],
        [
            "Pending lifetime",
            "PHOTO_BATCH_TTL_MINUTES defaults to 30. Countdown is server-synchronized. Finalization is refused at expiry even before physical cleanup.",
        ],
        [
            "Cleanup",
            "Cancellation removes pending files immediately. Startup, opportunistic checks and a cleanup service remove expired batches. PHOTO_BATCH_CLEANUP_INTERVAL_MINUTES defaults to 60.",
        ],
    ],
    [1.4, 5.7],
)
head("Upload progress and gallery management")
para(
    "Selection reports file count and total size. Save begins one aggregate multipart progress bar, followed by processing and cropping. Corrected retries retain progress behavior. At five official photos, file selection is disabled; over-capacity multi-file selections are still rejected by the server. Management cards use bounded 4:3 previews; missing images receive styled placeholders."
)
head("Organization assets")
table(
    [
        ["Asset", "Input / crop", "Generated output"],
        ["Logo", "JPG/PNG; square selection", "512 x 512 PNG, preserving transparency"],
        [
            "Banner",
            "JPG/PNG/HEIC/HEIF; configured ratio",
            "1920 x 640 progressive JPG by default",
        ],
        ["Favicon", "JPG/PNG; square selection", "32 x 32 and 180 x 180 PNG variants"],
    ],
    [0.85, 2.65, 3.6],
)
para(
    "Branding uses the same fixed-image 3 x 3 selector without stretching non-square sources. Preview and final uploads report progress. Image changes start the same configured timer; name/color-only changes do not. Preview responses create no pending stored files. Discard releases browser selections. Saved branding changes only after Save succeeds. Favicon fallback is dedicated icon, then logo, then a color-matched heart.",
    "small",
)

# 6
page("5. Volunteer contributions and hours")
head("Submission and review")
para(
    "Volunteers submit observations, temperament/good-with suggestions, notes and candidate photos. My submissions shows Pending, Approved and Rejected tabs scoped to the signed-in account, including previews and review outcomes."
)
bullets(
    [
        "Up to five candidate photos may be submitted, regardless of the current official photo count. Candidates do not reserve gallery positions or become public automatically.",
        "After the complete upload succeeds, each candidate is cropped before the proposal enters the staff review queue.",
        "Employees and Administrators review actual candidate previews beside the current official gallery. They select candidates to add and official photos to remove.",
        "Approval locks the submission and animal, recalculates capacity, and rejects a result above five official photos. Multiple pending submissions are therefore checked against current gallery state at each approval.",
    ]
)
head("Accumulated Total Hours")
para("Displayed total = recorded activity sum + manual adjustment.", "note")
para(
    "Administrators replace a Volunteer account's Total Hours through Manage users. The adjustment becomes the entered total minus the sum of recorded activities. Entries are never rewritten by this operation. Employees and Administrators can add, edit or delete individual activities, with a separate acknowledgement page for deletion."
)
table(
    [
        ["Example action", "Activity sum", "Adjustment", "Total"],
        ["Recorded entries", "8 h", "0 h", "8 h"],
        ["Administrator enters 20", "8 h", "+12 h", "20 h"],
        ["An activity changes from 5 to 7", "10 h", "+12 h", "22 h"],
        ["That 7-hour entry is deleted", "3 h", "+12 h", "15 h"],
    ],
    [3.05, 1.15, 1.45, 1.45],
)
para(
    "Activity and replacement-total inputs reject negative numbers. The stored adjustment is intentionally signed: replacing 5 recorded hours with a total of 2 stores -3. Later activity changes preserve that adjustment, so calculated totals are not silently clamped."
)
head("Role changes preserve volunteer records")
para(
    "Reassigning Volunteer to Employee or Administrator preserves all activities and the adjustment but hides Volunteer Hours for that account. It also leaves the volunteer-management list. Restoring Volunteer makes the preserved total visible again. The Total Hours replacement control is enabled only for Volunteer accounts."
)

# 7
page("6. Docker deployment and configuration")
table(
    [
        ["Service", "Responsibility", "Persistence / exposure"],
        [
            "app",
            "Django/Uvicorn, guarded initialization, seed and health endpoint",
            "./uploads bind mount; loopback-only host port",
        ],
        [
            "cleanup",
            "Expired pending-photo cleanup loop",
            "Same ./uploads folder and database; no published port",
        ],
        [
            "db",
            "PostgreSQL 17 with health check",
            "./postgres-data bind mount; no published database port",
        ],
    ],
    [0.85, 3.05, 3.2],
)
code("""./uploads        -> /app/uploads
./postgres-data  -> /var/lib/postgresql/data
PGDATA           -> /var/lib/postgresql/data/pgdata

127.0.0.1:${TAILTRAILS_PORT:-8000}:8000
[::1]:${TAILTRAILS_PORT:-8000}:8000""")
para(
    "All persistent data stays in folders beside docker-compose.yml. There are no named Docker volumes. PGDATA uses a child directory so metadata files at the mount root do not prevent initialization. Host port and UID/GID are configured in .env."
)
head("Reverse proxy")
para(
    "apache.example.conf and nginx.example.conf show a dedicated HTTPS subdomain with HTTP redirection, certificate paths, HSTS and a loopback upstream. Set the real hostname/certificates and configure TRUSTED_HOSTS, CSRF_TRUSTED_ORIGINS and COOKIE_SECURE=true. The application trusts forwarded scheme/host information and leaves redirect/HSTS policy to the proxy. A containerized proxy uses app:8000 over the Compose network instead of host loopback."
)
head("Key environment controls")
table(
    [
        ["Variables", "Purpose"],
        [
            "PHOTO_WEB_WIDTH / HEIGHT / QUALITY",
            "Animal web-image dimensions and JPG quality",
        ],
        [
            "MAX_PHOTO_SIZE_MB / MAX_REQUEST_SIZE_MB",
            "Per-file and complete request limits",
        ],
        ["PHOTO_BATCH_TTL_MINUTES", "Pending crop lifetime (30 minutes by default)"],
        [
            "PHOTO_BATCH_CLEANUP_INTERVAL_MINUTES",
            "Expired-file cleanup interval (60 minutes by default)",
        ],
        [
            "BRANDING_LOGO_SIZE / BRANDING_BANNER_WIDTH / HEIGHT",
            "Processed branding dimensions",
        ],
        [
            "BRANDING_WEB_QUALITY / BRANDING_MAX_SIZE_MB",
            "Branding JPG quality and per-file size limit",
        ],
    ],
    [3.5, 3.6],
)
head("Start and verify")
code("""cp .env.example .env
# Set unique secrets and deployment values first.
docker compose up --build -d
curl http://127.0.0.1:8000/healthz""")

# 8
page("7. Fresh installation and operations")
head("Fresh-install baseline")
para(
    "Use a new installation directory and empty database/upload folders. This build cannot upgrade or import an earlier prototype database.",
    "note",
)
bullets(
    [
        "The single 0001_fresh_baseline Django migration creates current models and deceased-status protection directly. No previous schema transformations, retired columns or experimental log tables remain.",
        "initialize_database checks for an empty database or this baseline's matching schema. Earlier/untracked schemas are refused before modification; it does not erase data or fake migrations.",
        "For a previous deployment, back up and stop its services, preserve its original folders separately, and start this build from a newly extracted directory with its own data folders.",
        "Do not copy old database/upload folders or restore an old SQL dump into this baseline. README.md describes setup and returning to the earlier installation if needed.",
        "Restarting this same baseline reuses its data. Validated demo seeding skips populated databases, so deletions and staff edits stay in place.",
    ]
)
head("System information")
para(
    "An administrator-only read-only page reports build/Python/Django versions, timezone, database connectivity/latency/migration, upload path/free disk capacity, image limits, CPU name/logical count/load, uptime, process memory, RAM and swap. Memory/storage use IEC units such as GiB and TiB. Values are container-visible and may reflect cgroup limits or host-kernel values."
)
para(
    "Authenticated Server-Sent Events update cards without full page refresh. The refresh menu offers 1, 2 or 5 seconds, defaulting to 5; it retains the interval in the URL, pauses in hidden tabs and reconnects after interruptions. A static snapshot remains available without JavaScript."
)
head("Release verification")
if args.verified_tests is not None:
    para(
        f"{args.verified_tests} Django tests passed on Python {PYTHON} with SQLite for this release. Coverage includes required medical selections, rejection of negative quantities, fresh-install/refusal/restart behavior, schema cleanup, permanent status, permissions, image processing, approval capacity, hours and deployment configuration."
    )
else:
    para(
        "Run the Django suite and optional JavaScript input checks before publishing a release. Do not infer test completion from generating this document."
    )
para(
    "JavaScript interaction checks exercise unsigned typing/paste and precision handling. Full browser checks could not run because this workspace prevented Chromium from launching. Docker/PostgreSQL runtime checks are also unavailable; SQLite tests do not substitute for a deployment smoke test.",
    "small",
)
code("""# Automated checks (Python environment + locked dependencies)
DB_ENGINE=sqlite python manage.py test
node tests/test_unsigned_inputs.js  # Optional; requires Node.js

# Maintenance
# Remove expired pending uploads immediately
docker compose exec app python manage.py cleanup_photo_batches""")
para(
    "See README.md for deployment, GIT_WORKFLOW.md for source imports/tags, and CONTRIBUTING.md for collaboration. VERSION supplies the build identifier. The optional PDF generator reads it directly.",
    "small",
)

SimpleDocTemplate(
    str(args.output),
    pagesize=letter,
    leftMargin=47,
    rightMargin=47,
    topMargin=44,
    bottomMargin=58,
    title=f"Tail Trails Architecture Overview - {VERSION}",
    author="Tail Trails Prototype",
).build(story, onFirstPage=footer, onLaterPages=footer)
print(args.output)
