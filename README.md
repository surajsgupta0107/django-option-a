# Server Utilization Portal — Django Edition, Option A (React, Django-served)

Standalone project: Django + DRF backend + Celery + Postgres, with the React frontend
built once and served through Django itself — one project, one command, one port.

| | URL |
|---|---|
| App | `http://localhost:8000/` |
| REST API | `http://localhost:8000/api/` |
| Django admin | `http://localhost:8000/admin/` |

> **This is the recommended option.** See "Why this one" below for the reasoning, or
> just compare it directly against `django-option-b` (classic Django templates) —
> same backend, same data, genuinely different frontend approach.

> **Heads up:** built and syntax-checked in a sandbox with no outbound network access,
> so it hasn't been run end-to-end yet. Treat first setup as a normal shakeout pass and
> tell me exactly what breaks.

## Why this one

For a dashboard this data-dense and interactive — live charts, instant filtering,
sortable tables, modals, bulk actions — a SPA frontend talking to a REST/JSON API is
the standard, correct architecture for the job, not just the nicer-looking choice.
Classic server-rendered templates (see `django-option-b`) are the right call when an
app is mostly simple forms and full-page reloads are fine; recreating this app's UX
there means permanently maintaining a second, lesser copy of the same interface by
hand. This option gets you the actual goal — one project, one command to run
everything — without that tradeoff.

## Windows setup

### Docker Desktop (recommended)

1. Install **Docker Desktop for Windows**: https://www.docker.com/products/docker-desktop/ (accept WSL2 if prompted)
2. Install **Node.js LTS**: https://nodejs.org/, then build the frontend *before* starting Docker:
   ```powershell
   cd frontend
   npm install
   npm run build
   cd ..
   ```
   This outputs into `static/react/`.
3. From the project root:
   ```powershell
   copy .env.example .env
   docker compose up --build
   ```
4. Open `http://localhost:8000/`.

To create a Django admin superuser (optional): `docker compose exec api python manage.py createsuperuser`

Stop with `Ctrl+C` then `docker compose down` (add `-v` to also wipe the Postgres volume).

### Native Python (no Docker)

Uses SQLite instead of Postgres and skips Celery/Redis — reminders will queue but not
process without a worker running.

1. Install **Python 3.12**: https://www.python.org/downloads/windows/ (check "Add python.exe to PATH")
2. In PowerShell, from this folder:
   ```powershell
   python -m venv venv
   venv\Scripts\Activate.ps1
   ```
   (If blocked: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`, then retry.)
3. ```powershell
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py runserver
   ```
4. Build the frontend (separate PowerShell window, Node.js LTS installed):
   ```powershell
   cd frontend
   npm install
   npm run build
   ```
   `runserver` picks up the built files automatically — no restart, no `collectstatic` needed in DEBUG mode.
5. Visit `http://localhost:8000/`.

Reminder emails log to the terminal running `runserver`/Celery when `SMTP_HOST` is blank.

## Actively developing the frontend?

Use `django-option-c` instead — same source, run via Vite's dev server with hot reload
rather than a full rebuild per change. Switch back here (rebuild + `runserver`) once
you're done iterating.

## How this works

`frontend/vite.config.js` builds straight into `static/react/` with fixed, unhashed
filenames (`index.js`, `index.css`) so `templates/react_app.html` can reference them
directly — no manifest-parsing needed for local dev. Tradeoff: weaker browser
cache-busting on redeploys; add hashed filenames + Django's manifest storage back in
if that starts to matter at your traffic volume.

Under Docker, the app runs behind **gunicorn**, which — unlike `runserver` — doesn't
serve static files on its own. **WhiteNoise** is wired in (see `MIDDLEWARE` and
`STORAGES` in `config/settings.py`) so `collectstatic` (run automatically by the
Dockerfile) bundles everything gunicorn needs to serve the frontend correctly there.

## What you're looking at

```
django-option-a/
├── config/                     Django project settings, urls, Celery app
├── servers_app/
│   ├── models.py                Server, Reminder, Response, ThresholdConfig, etc.
│   ├── services.py               Shared KPI computation used by the dashboard API
│   ├── views.py / urls.py        REST API (DRF)
│   └── migrations/0001_initial.py   Hand-authored, field-checked against models.py
├── templates/react_app.html    One-line HTML shell that mounts the built React app
├── static/                     React build output lands in static/react/ (gitignored — build it yourself)
├── frontend/                   React + Vite source
├── docker-compose.yml          Postgres + Redis + API + Celery worker + beat
├── requirements.txt
├── .env.example
└── sample-data-enriched.xlsx   Your real sample data, ready to upload
```

## What's stubbed vs. real (Phase 1 scope)

- **Admin auth** is a single shared API key (`ADMIN_API_KEY`), not real SSO — sent as `X-API-Key` on API requests.
- **Owner identity**: the real, token-based flow is now fully implemented — reminder emails link to `/owner-response?token=...`, which renders a standalone page (`OwnerResponsePage` in `frontend/src/ServerUtilizationApp.jsx`, routed in `main.jsx`) that calls the token-based `/api/responses/lookup` and `/api/responses/submit` endpoints, no admin key or login involved. The admin app's own "Owner Portal" tab still uses the separate dropdown-based `*-dev` endpoints as a convenience for demoing the workflow without needing a real email round-trip — that one's still a deliberate shortcut, not a bug.
- **Email** logs to the console/terminal if `SMTP_HOST` is blank.
- **Upload replaces the whole dataset** each time rather than merging.
- **Migration file is hand-authored**, not `makemigrations`-generated (Django wasn't installable offline). Verified field-for-field against `models.py` by script, but if you add/change a model field, run `python manage.py makemigrations servers_app` yourself going forward.

## API reference

| Endpoint | Notes |
|---|---|
| `GET /api/servers` | List + filter (`application`, `owner`, `environment`, `company`, `status`, `search`, `needs_reminder`) |
| `GET /api/servers/{id}` | Full detail incl. reminder/response history |
| `GET /api/servers/meta/filters` | Distinct values for filter dropdowns |
| `POST /api/servers/upload` | CSV/XLSX upload (admin only) |
| `GET /api/servers/export/csv` | Export current dataset |
| `GET/PUT /api/thresholds` | View/update the underutilization rule (admin only to update) |
| `POST /api/reminders/server/{id}` / `POST /api/reminders/bulk` | Queues reminder email(s) via Celery (admin only) |
| `GET /api/responses/lookup?token=...` | Resolves a reminder-link token to server details, no login |
| `POST /api/responses/submit?token=...` | Owner submits keep/downsize/decommission + comment |
| `GET /api/dashboard/kpis` | Aggregated KPIs + chart data |

Admin-only routes expect header `X-API-Key: <ADMIN_API_KEY>`.

## If something breaks

1. **Blank page / 404s on CSS or JS** — you likely skipped `npm run build`, or it landed somewhere other than `static/react/`. Check that `static/react/index.js` exists.
2. A pinned package version in `requirements.txt` that's since changed — try relaxing the pin.
3. Docker Desktop not fully started before `docker compose up` — give it a minute.
4. Port conflicts (8000, 5173, 5432, 6379 need to be free).

Tell me the exact error and I'll fix it directly.
