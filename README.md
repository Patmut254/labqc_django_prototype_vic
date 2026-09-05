# Laboratory Quality Control System (Django prototype)

Digital artefact for the dissertation "Digitalising Construction Material
Test Documentation in Nigeria" — implements the three-tier architecture
from Chapter 4 (presentation / application / database layers) as a real
running web application, in place of the earlier spreadsheet artefact.

The database is already seeded with the same 20-sample demonstration
dataset used in Chapter 6, so all figures (20 samples, 20 slump tests,
38 strength tests, 3 slump non-conformances, 3 failed 28-day results)
match the dissertation exactly.

## Requirements

- Python 3.10+
- pip

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install django openpyxl
pip install dj-database-url psycopg[binary]
python manage.py runserver
```

Then open http://127.0.0.1:8000/ in a browser.

The database (`db.sqlite3`) is included, already populated — no need to
run migrations or the seed command again unless you want to reset it:

```bash
# Only if you want to start from empty and reseed:
rm db.sqlite3
python manage.py migrate
python manage.py seed_from_excel seed_source.xlsx
```

## Deploying to Vercel

This repo now includes `vercel.json`, `build_files.sh`, and a `requirements.txt`
so it can be deployed as-is:

1. Push this folder to a GitHub repo and import it in Vercel.
2. In the Vercel project's **Environment Variables**, set:
   - `DJANGO_SECRET_KEY` — any long random string (don't reuse the dev key
     committed in `settings.py`).
   - `DJANGO_DEBUG` — `False`.
   - `DATABASE_URL` — *(recommended, see warning below)* a Postgres
     connection string from Vercel Postgres, Neon, or Supabase.
3. Set **Build Command** to `bash build_files.sh` if Vercel doesn't pick it
   up automatically.
4. Deploy. `ALLOWED_HOSTS` already accepts any `*.vercel.app` domain and the
   deployment's own `VERCEL_URL` automatically.

**⚠️ SQLite warning:** Vercel's serverless functions have a read-only
filesystem outside `/tmp`, and `/tmp` is wiped between invocations. If you
deploy without setting `DATABASE_URL`, the app will run and the seeded
20-sample dataset will display correctly, but anything a user registers or
tests *after* deployment (new samples, new results) may disappear on the
next request. For a live, client-facing demo where they'll actually use the
data-entry forms, set `DATABASE_URL` to a real Postgres instance first —
`python manage.py migrate` and `python manage.py seed_from_excel
seed_source.xlsx` will need to be run once against that database (e.g. by
setting `DATABASE_URL` locally too and running those two commands from your
machine before the first deploy).

If the presentation is just a read-only walkthrough of the existing 20
samples, the bundled SQLite file is fine to deploy without a separate
database.

```
$env:DATABASE_URL="postgresql://neondb_owner:npg_7Hqn2KXtOUjs@ep-dark-band-aeofg1r7-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
python manage.py migrate
python manage.py seed_from_excel
```

## Login accounts

| Username   | Password  | Role                                |
| ---------- | --------- | ----------------------------------- |
| technician | labqc2026 | Lab Technician                      |
| engineer   | labqc2026 | Site Engineer                       |
| manager    | labqc2026 | Project Manager                     |
| admin      | labqc2026 | Superuser (Django admin at /admin/) |

`user1`–`user10` (password `labqc2026`) are also created, matching the
"User 1"–"User 10" technicians named in the original spreadsheet.

## Modules (map directly to Chapter 4's architecture)

- **Sample Registration** (`/registration/`) — assigns each batch a
  traceable Sample ID (SMP-000x), auto-generated on save.
- **Slump Test** (`/slump-test/`) — records slump readings, auto-flags
  results exceeding the grade's acceptance limit.
- **Curing and Strength** (`/curing-strength/`) — records load and
  cross-sectional area for the 7/14/21/28-day cycle; compressive
  strength is calculated automatically (load ÷ area), and 28-day
  results are checked against the grade's acceptance limit.
- **Reporting** (`/reporting/`) — summary metrics, a compressive
  strength development chart, and the auto-generated non-conformance
  log, restricted to what each role needs to see.

Role-based dashboards restrict what each user sees, per Chapter 4.2.

## Notes on the tech stack (for Chapter 5.1)

- **Backend/frontend:** Django (server-rendered templates — no separate
  frontend framework), matching the "single browser-based application"
  requirement.
- **Database:** SQLite for this prototype; the same models would run on
  PostgreSQL/MySQL for production without changes, supporting Chapter
  4.4's point about flexible hosting (cloud or on-site).
- **Charting:** Chart.js, bundled locally as a static file (not loaded
  from a CDN) so the reporting dashboard works even without an internet
  connection during a live demonstration.
- **Data entry pages render as tables/grids**, not multi-page forms —
  this preserves the design rationale in Chapter 4.5, where technicians
  interviewed preferred a spreadsheet-like layout over conventional
  forms.
