# Tail Trails Git and release workflow

This guide keeps the Git repository, application build number, release ZIP, deployment, and documentation aligned.

## Choose your shell

| Platform | Instructions |
| --- | --- |
| Linux or macOS Terminal (Bash/zsh) | Use the Linux/macOS section with Git, unzip and rsync available. |
| Windows PowerShell | Use the Windows section with Git for Windows and PowerShell; ZIP synchronization uses Robocopy. |
| Windows Git Bash | The shell commands can be used if unzip and rsync are also installed; otherwise use PowerShell. |

Git configuration and repository operations work across platforms. Importing and committing packaged source does not require Python or SQLite. Development, testing and dependency refreshes require the project Python tools; Docker is needed to run/deploy the containers. Paths below are examples; substitute your own.

## Required utilities and dependencies

Choose the row for the work you are doing. These tools are for source maintainers and people deploying the application. Staff, volunteers and public visitors using a deployed site need a web browser; they do not need Git or developer tools.

### Requirements by task

| Task | Required on your computer | Additional notes |
| --- | --- | --- |
| Clone, commit, branch, tag, pull or push | Git 2.28 or newer and your platform's shell | Network access and repository credentials are needed for remote operations. |
| Import a generated ZIP on Linux/macOS | Git, Bash/zsh, `unzip`, `rsync`, and the standard `cat`, `cp`, `mktemp`, `printf` utilities | The commands below stage, preview and synchronize the extracted source. |
| Import a generated ZIP on Windows PowerShell | Git for Windows, PowerShell 5.1 or 7, and Windows Robocopy | ZIP extraction and file/path operations use built-in PowerShell commands. No separate ZIP application is needed. |
| Import a generated ZIP in Windows Git Bash | Git Bash plus the same commands listed for Linux/macOS | Check `unzip` and `rsync` explicitly; use the PowerShell workflow if they are unavailable. |
| Create a release ZIP from a Git tag | Git and the selected shell | `git archive` creates the ZIP; a separate `zip` utility is not required. |
| Edit source, `VERSION` or `.env` | A plain-text editor | Use a code/plain-text format when saving files. |
| Build/run/deploy with Compose | Docker CLI, a running Docker Engine, and the Compose plugin providing `docker compose` | Docker Desktop supplies these together; Linux can also use Engine with the Compose plugin. Use Linux containers. Git is needed if deploying from a Git clone. |
| Check the running health endpoint | Linux/macOS: `curl`; Windows: PowerShell `Invoke-RestMethod` | These are used only for the health-check commands. |
| Run Django tests on the host | Python 3.14 with `venv`, `pip`, the Python `sqlite3` module, and packages from `requirements.lock` | The documented test command uses an isolated SQLite database. |
| Run the application directly on the host | Python 3.14 with `venv`, `pip` and packages from `requirements.lock`, plus the configured database connection | Local SQLite development needs Python's `sqlite3` module. PostgreSQL mode needs access to a PostgreSQL server. |
| Refresh `requirements.lock` | `uv` and the project's Python tooling | Required for the `uv pip compile` line, not for ordinary Git operations. |
| Run optional JavaScript checks | Node.js | The shown checks use Node's built-in modules; no npm install step is required. |
| Generate the overview PDF | Python and the `reportlab` package | Install ReportLab with `python -m pip install reportlab`; it is not an application runtime requirement. |
| Publish behind HTTPS | A configured reverse proxy such as Apache or Nginx and a certificate | Follow README.md and the supplied proxy examples. This is not required to import source or make Git commits. |

**Importing and committing a pre-made ZIP requires no Python, SQLite installation, Docker, Node.js, `uv` or ReportLab.** Install only the source-import tools for your platform. The SQLite command-line program is not needed for the test workflow either; tests use Python's `sqlite3` module. Compose provides the application's Python packages and PostgreSQL inside containers, so the Docker workflow does not require host application packages or a host PostgreSQL installation.

The Linux/macOS branch workflow includes a dependency-lock refresh command. Install `uv` before running that line, or skip that line when you are not refreshing dependencies. The Python test commands are also optional for packaged-source imports.

### Platform readiness checks

**Linux and macOS Terminal:** use Bash or zsh. Run the following before the ZIP-import workflow; any `Missing:` line identifies a utility to install using your platform's package manager or official installer:

```bash
for utility in git cat cp mktemp printf unzip rsync; do
  command -v "$utility" >/dev/null 2>&1 || printf 'Missing: %s\n' "$utility"
done
git --version
```

These checks also apply to Git Bash. Do not assume every Unix utility is present just because Git itself is installed.

**Windows PowerShell:** install Git for Windows and use PowerShell 5.1 or PowerShell 7. Robocopy is supplied by Windows; the remaining listed file/archive commands are PowerShell commands:

```powershell
$PSVersionTable.PSVersion
git --version
Get-Command git, robocopy, Expand-Archive, Get-Content, Set-Content, Join-Path, New-Item, Test-Path, Remove-Item
```

**Docker deployment, on any platform:** confirm that both the CLI/plugin and the engine are available before using deployment commands:

```text
docker --version
docker compose version
docker info
```

Docker Desktop must be running when using its engine. On Linux with Docker Engine, the Docker service must be running and your account must be able to access it. For the example health check, Linux/macOS users can check `curl --version`; PowerShell users can check `Get-Command Invoke-RestMethod`.

**Optional development tools:** run only the checks relevant to the tasks you selected above:

| Tool or capability | Availability check |
| --- | --- |
| Project Python | `python --version` (the application targets Python 3.14) |
| pip | `python -m pip --version` |
| Python virtual environments and SQLite module | `python -c "import venv, sqlite3; print(sqlite3.sqlite_version)"` |
| Installed application packages | `python -m pip check` after installing `requirements.lock` |
| Dependency resolver | `uv --version` |
| JavaScript checks | `node --version` |
| PDF generation | `python -c "import reportlab; print(reportlab.Version)"` |

Use the project's Python environment for local tests. Install its packages with `python -m pip install --require-hashes -r requirements.lock`; see README.md for environment setup. Some Python distributions package `venv` or pip separately, so check those capabilities as well as the interpreter version.

### Installation references

Use the official installation instructions for the tool and your platform:

- [Git installation](https://git-scm.com/install/) and [Git for Windows](https://gitforwindows.org/)
- [PowerShell installation](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell)
- [Docker Compose installation options](https://docs.docker.com/compose/install/)
- [Python downloads](https://www.python.org/downloads/)
- [uv installation](https://docs.astral.sh/uv/getting-started/installation/)
- [Node.js downloads](https://nodejs.org/en/download)

For Linux/macOS command-line utilities such as `unzip`, `rsync` and `curl`, use your operating system's package manager when they are missing.

## Repository safety

The repository tracks source code and empty persistence-folder placeholders. It must not track:

- `.env` or secrets
- `uploads/` contents
- `postgres-data/` contents
- SQLite runtime databases under `data/`
- Python caches or collected static files

The included `.gitignore` already protects these paths. Verify with `git status --ignored` before the initial commit.

If Git identity has not been configured, set the name and email to use for commits (the same commands work in all shells):

```text
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

## Linux and macOS shell workflow

Use these commands from Bash or zsh. Keep the same terminal session between ZIP preview and apply steps. Health-check examples assume port 8000 unless `TAILTRAILS_PORT` is set in your shell; use the host port configured in `.env`.

### Initial repository setup

From inside the extracted `tail-trails/` directory:

```bash
git init -b main
git add .
git commit -m "Initial import: Tail Trails $(cat VERSION)"
git remote add origin https://your-git-server/example/tail-trails.git
git push -u origin main
git tag -a "v$(cat VERSION)" -m "Tail Trails $(cat VERSION)"
git push origin "v$(cat VERSION)"
```

### One authoritative build number

The root `VERSION` file is the only application-version source. Django reads it directly, and the value appears in `/healthz`, HTML cache keys, and the administrator System Information page.

For a new iteration, change only `VERSION` before testing and committing:

```bash
printf '%s\n' '2026.11.17.4' > VERSION
```

Use the same value for the release commit, annotated Git tag, ZIP, and overview PDF. Do not add `APP_VERSION` to `.env` or Compose.

### Normal branch and release workflow

```bash
git switch main
git pull --ff-only
git switch -c release/$(cat VERSION)

# Apply and review changes.
uv pip compile requirements.in --python-version 3.14 --universal --generate-hashes --output-file requirements.lock
git status --short
git diff --check
# Optional: run tests if Python and the project dependencies are installed.
# DB_ENGINE=sqlite python manage.py test

git add -A
git commit -m "Release $(cat VERSION)"
git push -u origin "release/$(cat VERSION)"
```

Merge the release branch through the repository's normal review process. Tag the merge commit on `main`:

```bash
git switch main
git pull --ff-only
git tag -a "v$(cat VERSION)" -m "Tail Trails $(cat VERSION)"
git push origin main --follow-tags
```

### Updating a repository from a generated ZIP

When a ZIP is the delivery source, stage it before synchronizing the repository. Do not extract directly over the working tree.

```bash
cd /path/to/repository/tail-trails
stage_dir=$(mktemp -d)
unzip /path/to/Tail_Trails_Django_PostgreSQL_Prototype.zip -d "$stage_dir"

rsync -avhn --delete \
  --exclude='.git/' \
  --exclude='.env' \
  --exclude='uploads/' \
  --exclude='postgres-data/' \
  --exclude='data/' \
  "$stage_dir/tail-trails/" ./
```

Review the dry run, especially deletions, then repeat without `-n`:

```bash
rsync -avh --delete \
  --exclude='.git/' \
  --exclude='.env' \
  --exclude='uploads/' \
  --exclude='postgres-data/' \
  --exclude='data/' \
  "$stage_dir/tail-trails/" ./

git status --short
git diff --check
# Optional validation when importing a pre-made ZIP; safe to skip this whole command.
# DB_ENGINE=sqlite python manage.py test
git add -A
git commit -m "Release $(cat VERSION)"
git tag -a "v$(cat VERSION)" -m "Tail Trails $(cat VERSION)"
git push origin main --follow-tags
```

`git add -A` stages additions, modifications and deletions.

The commented test command is optional when committing a pre-made ZIP. Git does not require Python, SQLite, or the application dependencies. To run the tests locally, install the project's Python version and dependencies first; SQLite support is normally included with Python. `DB_ENGINE=sqlite` applies only to that command and selects an isolated test database. It does not change `.env` or the deployed PostgreSQL database. Skip the entire command if you are only importing and committing the ZIP; removing just `DB_ENGINE=sqlite` would run the tests against the default PostgreSQL configuration.

### Generate a release ZIP from a tag

After tagging the release, generate a clean archive containing only tracked files:

```bash
git archive \
  --format=zip \
  --prefix=tail-trails/ \
  --output=Tail_Trails_Django_PostgreSQL_Prototype.zip \
  "v$(cat VERSION)"
```

The `tail-trails/` prefix preserves the expected extraction folder. Runtime data, `.env`, and `.git` are excluded automatically because they are not tracked.

### Deploy from Git

Clone the repository and check out the verified release tag:

```bash
git clone https://your-git-server/example/tail-trails.git tail-trails
cd tail-trails
git checkout "v$(cat VERSION)"
cp .env.example .env
# Set unique secrets, host/proxy settings and the desired host port.
docker compose up --build -d
curl http://127.0.0.1:${TAILTRAILS_PORT:-8000}/healthz
```

Startup applies the Django schema and seeds demo records when the database is empty. Runtime folders persist across application restarts.

When using a release tag different from the default branch, check out that exact tag before configuring and starting the services. Use `git switch main` before resuming development after a detached-tag checkout.

## Windows PowerShell workflow

Use PowerShell on Windows with Git for Windows installed. These examples work with Windows PowerShell 5.1 or PowerShell 7. Run the commands from the extracted `tail-trails` project directory unless a step specifies another location. Keep the same PowerShell session between the preview and apply steps so their variables remain available.

### Initial repository setup

```powershell
Set-Location 'C:\Projects\tail-trails'
$version = (Get-Content -LiteralPath .\VERSION -Raw).Trim()
git init -b main
git add .
git commit -m "Initial import: Tail Trails $version"
git remote add origin https://your-git-server/example/tail-trails.git
git push -u origin main
git tag -a "v$version" -m "Tail Trails $version"
git push origin "v$version"
```

### One authoritative build number

`VERSION` supplies the application, health endpoint, static cache keys and overview PDF. Set it when preparing a release, then read its value into the PowerShell variable used by Git commands:

```powershell
Set-Content -LiteralPath .\VERSION -Value '2026.11.17.4' -Encoding ascii
$version = (Get-Content -LiteralPath .\VERSION -Raw).Trim()
```

The explicit ASCII encoding keeps the version file free of a byte-order mark in both PowerShell editions. Do not add a second build-number setting to `.env` or Compose.

### Normal branch and release workflow

```powershell
git switch main
git pull --ff-only
# Set VERSION to the release number, then read it again.
$version = (Get-Content -LiteralPath .\VERSION -Raw).Trim()
git switch -c "release/$version"

# Apply and review the changes.
# For dependency changes, refresh the lock with the project's Python tools:
# uv pip compile requirements.in --python-version 3.14 --universal --generate-hashes --output-file requirements.lock
git status --short
git diff --check
# Optional project testing is described below.
git add -A
git commit -m "Release $version"
git push -u origin "release/$version"
```

After merging the reviewed branch, tag the release on `main`:

```powershell
git switch main
git pull --ff-only
$version = (Get-Content -LiteralPath .\VERSION -Raw).Trim()
git tag -a "v$version" -m "Tail Trails $version"
git push origin main --follow-tags
```

### Updating a repository from a generated ZIP

Start with a clean working tree, or commit/stash local changes first. Extract into a temporary directory and verify the project root before synchronizing. Robocopy is the Windows copy tool used here; Python, SQLite, Bash and rsync are not required for this source-import workflow.

```powershell
Set-Location 'C:\Projects\tail-trails'
$repoDir = (Get-Location).Path
if (-not (Test-Path -LiteralPath (Join-Path $repoDir '.git'))) {
    throw 'Run this from the root of the Tail Trails Git repository.'
}
git status --short

$zipPath = 'C:\Downloads\Tail_Trails_Django_PostgreSQL_Prototype.zip'
$stageDir = Join-Path ([System.IO.Path]::GetTempPath()) ('tail-trails-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stageDir -ErrorAction Stop | Out-Null
Expand-Archive -LiteralPath $zipPath -DestinationPath $stageDir -ErrorAction Stop
$sourceDir = Join-Path $stageDir 'tail-trails'
if (-not (Test-Path -LiteralPath (Join-Path $sourceDir 'VERSION') -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $sourceDir 'manage.py') -PathType Leaf)) {
    throw 'The ZIP must contain the tail-trails project folder.'
}

$copyOptions = @(
    '/E', '/PURGE', '/R:1', '/W:1', '/XJ',
    '/XD', '.git', 'uploads', 'postgres-data', 'data',
    '/XF', '.git', '.env'
)
robocopy $sourceDir $repoDir @copyOptions /L
if ($LASTEXITCODE -ge 8) { throw 'Robocopy preview failed. Do not continue.' }
```

Review the file list and planned deletions. `/L` lists actions without copying or deleting. The exclusions preserve Git metadata (including a worktree's `.git` file), `.env`, uploaded files and database folders. `/E /PURGE` synchronizes the application tree, including removal of destination source files absent from the ZIP. Use only the project repository as the destination.

After reviewing the preview, apply from the **same PowerShell session**:

```powershell
robocopy $sourceDir $repoDir @copyOptions
if ($LASTEXITCODE -ge 8) { throw 'Robocopy failed. Review the output before committing.' }

git status --short
git diff --check
# Optional: run project tests if Python and dependencies are installed.
$version = (Get-Content -LiteralPath .\VERSION -Raw).Trim()
git add -A
git commit -m "Release $version"
git tag -a "v$version" -m "Tail Trails $version"
git push origin main --follow-tags

Remove-Item -LiteralPath $stageDir -Recurse -Force
```

Robocopy uses nonzero status codes for some successful operations; codes of 8 or greater indicate a copy failure. The explicit checks above allow its normal status codes while stopping the workflow on failure.

### Optional Python test command

Skip this entire block when only importing/committing the packaged source. Running tests requires the project Python version and locked dependencies to be installed in your active Python environment:

```powershell
$savedDbEngine = $env:DB_ENGINE
try {
    $env:DB_ENGINE = 'sqlite'
    python manage.py test
}
finally {
    $env:DB_ENGINE = $savedDbEngine
}
```

This selects an isolated SQLite test database and restores the session environment afterward. It does not edit `.env`. Git operations alone do not require Python or SQLite.

### Generate a release ZIP from a tag

```powershell
$version = (Get-Content -LiteralPath .\VERSION -Raw).Trim()
git archive --format=zip --prefix=tail-trails/ --output=Tail_Trails_Django_PostgreSQL_Prototype.zip "v$version"
```

The archive contains tracked files under `tail-trails/`. Keep runtime folders and secrets untracked using the supplied `.gitignore`.

### Deploy from Git

With Git and Docker Compose available:

```powershell
git clone https://your-git-server/example/tail-trails.git tail-trails
Set-Location .\tail-trails
$version = (Get-Content -LiteralPath .\VERSION -Raw).Trim()
git checkout "v$version"
Copy-Item -LiteralPath .\.env.example -Destination .\.env
# Set unique secrets, host/proxy settings and the desired host port in .env.
docker compose up --build -d
docker compose ps
$port = 8000 # Match TAILTRAILS_PORT in .env.
Invoke-RestMethod -Uri "http://127.0.0.1:$port/healthz"
```

Choose the exact release tag before configuring and starting services. Use `git switch main` before returning to development. Compose manages database initialization and keeps the local database/upload folders across restarts.

## Command references

- [Microsoft: Robocopy options and return codes](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy)
- [Microsoft: Expand-Archive](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.archive/expand-archive?view=powershell-5.1)
- [Microsoft: Set-Content encodings](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/set-content?view=powershell-5.1)
