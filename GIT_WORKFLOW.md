# Tail Trails Git and release workflow

This guide keeps the Git repository, application build number, release ZIP, deployment, and documentation aligned.

## Repository safety

The repository tracks source code and empty persistence-folder placeholders. It must not track:

- `.env` or secrets
- `uploads/` contents
- `postgres-data/` contents
- SQLite runtime databases under `data/`
- Python caches or collected static files

The included `.gitignore` already protects these paths. Verify with `git status --ignored` before the initial commit.

## Initial repository setup

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

## One authoritative build number

The root `VERSION` file is the only application-version source. Django reads it directly, and the value appears in `/healthz`, HTML cache keys, and the administrator System Information page.

For a new iteration, change only `VERSION` before testing and committing:

```bash
printf '%s\n' '2026.11.16.13' > VERSION
```

Use the same value for the release commit, annotated Git tag, ZIP, and overview PDF. Do not add `APP_VERSION` to `.env` or Compose.

## Normal branch and release workflow

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

## Updating a repository from a generated ZIP

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

`git add -A` is intentional: it records deleted obsolete source files as well as additions and edits.

The commented test command is optional when committing a pre-made ZIP. Git does not require Python, SQLite, or the application dependencies. To run the tests locally, install the project's Python version and dependencies first; SQLite support is normally included with Python. `DB_ENGINE=sqlite` applies only to that command and selects an isolated test database. It does not change `.env` or the deployed PostgreSQL database. Skip the entire command if you are only importing and committing the ZIP; removing just `DB_ENGINE=sqlite` would run the tests against the default PostgreSQL configuration.

## Generate a release ZIP from a tag

After tagging the release, generate a clean archive containing only tracked files:

```bash
git archive \
  --format=zip \
  --prefix=tail-trails/ \
  --output=Tail_Trails_Django_PostgreSQL_Prototype.zip \
  "v$(cat VERSION)"
```

The `tail-trails/` prefix preserves the expected extraction folder. Runtime data, `.env`, and `.git` are excluded automatically because they are not tracked.

## Deploy from Git

For a deployment checkout, preserve `.env`, `uploads/`, `postgres-data/`, and `data/`, then move to the verified tag:

```bash
git fetch --tags --prune
release_tag=vYYYY.MM.DD.N
git checkout "$release_tag"
docker compose build --no-cache app cleanup
docker compose up -d --force-recreate
curl http://127.0.0.1:${TAILTRAILS_PORT:-8000}/healthz
```

Container startup applies migrations automatically. Use `git switch main` before resuming development after a detached-tag deployment check.
