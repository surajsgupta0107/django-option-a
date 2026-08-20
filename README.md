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
4. Create your admin login (required now — there's no default/shared credential): `docker compose exec api python manage.py createsuperuser`
5. Open `http://localhost:8000/` and log in with that account.

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
5. Visit `http://localhost:8000/` and log in with the superuser account you just created.

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
│   ├── security.py               Real per-user auth checks + signed owner-link tokens
│   ├── views.py / urls.py        REST API (DRF) — auth, admin, and owner-scoped routes
│   └── migrations/               Hand-authored, field-checked against models.py
├── templates/react_app.html    One-line HTML shell that mounts the built React app
├── static/                     React build output lands in static/react/ (gitignored — build it yourself)
├── frontend/                   React + Vite source — Login, admin App, OwnerDashboard, OwnerResponsePage
├── docker-compose.yml          Postgres + Redis + API + Celery worker + beat
├── requirements.txt
├── .env.example
└── sample-data-enriched.xlsx   Your real sample data, ready to upload
```

## Accounts, roles, and how login works

There's no shared API key anymore — every request is tied to a real logged-in user
(DRF token auth). One login screen, one endpoint (`POST /api/auth/login`); the backend
decides Admin vs. Owner from the account's Django `is_staff` flag and returns it as
`role`, and the frontend routes accordingly:

- **Admin** (`is_staff=True`): sees the full dashboard app — everything that existed before.
- **Owner** (`is_staff=False`): sees a separate, much smaller "My Servers" dashboard, scoped to servers where `Server.owner_email` matches their account's email — full detail (utilization, allocation, reclaimable capacity, reminder history, past responses) and a respond form per server, no admin controls visible at all.

Create accounts via Django admin (`/admin/auth/user/add/`) or `python manage.py createsuperuser`
for the first admin. For an Owner account: leave "Staff status" unchecked and set
**Email** to exactly match that person's `owner_email` on their `Server` rows (case-insensitive).

The **emailed reminder link stays separate and login-free** — clicking it doesn't
require an account at all, just the signed token in the URL. Both paths exist on
purpose: the token link is the fastest way to respond to one reminder; a real account
is for an owner who wants to check on their servers proactively, any time, without
waiting for an email.

## Reminders: single-server vs. digest (multi-server) emails

`POST /api/reminders/bulk` now groups the selected servers by `owner_email` server-side.
An owner with only one selected server still gets the normal single-server email
(`ThresholdConfig.email_template`); an owner with several gets **one consolidated
email** listing all of them (`ThresholdConfig.email_template_digest`, editable from
Settings), with one response link covering the whole group. Every server still gets
its own `Reminder` row for accurate per-server tracking — they just share a `digest_id`
marking them as having come from the same actual email. This is automatic; there's no
separate "send as digest" toggle in the UI — select multiple servers for the same
owner and bulk-send does the right thing.

## What's stubbed vs. real (Phase 2 progress)

- **Admin & Owner auth** is now real per-user login (Django `auth.User` + DRF token auth) — not SSO/OIDC yet, but no more shared secret either. See `servers_app/security.py`.
- **Owner identity** on the token-link flow is unchanged and still real (signed, expiring tokens — now supporting multiple servers per token for digest reminders).
- **Email** logs to the console/terminal if `SMTP_HOST` is blank.
- **Upload replaces the whole dataset** each time rather than merging.
- **Migration files are hand-authored**, not `makemigrations`-generated (Django wasn't installable offline). Verified field-for-field against `models.py` by script, but if you add/change a model field, run `python manage.py makemigrations servers_app` yourself going forward.
- **Not yet done**: real SSO/OIDC, password reset flow, self-serve owner account creation (an admin still has to create Owner accounts manually via `/admin/`), rate-limiting on `/api/auth/login`.

## API reference

| Endpoint | Notes |
|---|---|
| `POST /api/auth/login` | `{username, password}` → `{token, username, email, role}` |
| `POST /api/auth/logout` | Invalidates the current token |
| `GET /api/auth/me` | Current logged-in user's info |
| `GET /api/servers` | Admin only. List + filter (`application`, `owner`, `environment`, `company`, `status`, `search`, `needs_reminder`) |
| `GET /api/servers/{id}` | Admin only. Full detail incl. reminder/response history |
| `GET /api/servers/meta/filters` | Admin only. Distinct values for filter dropdowns |
| `POST /api/servers/upload` | Admin only. CSV/XLSX upload |
| `GET /api/servers/export/csv` | Admin only. Export current dataset |
| `GET/PUT /api/thresholds` | GET is admin-only too now; PUT to change the rule (also admin only) |
| `POST /api/reminders/server/{id}` | Admin only. Single-server reminder |
| `POST /api/reminders/bulk` | Admin only. Owner-aware — see "digest emails" above |
| `GET /api/responses/lookup?token=...` | No login — resolves a reminder-link token to one or more servers |
| `POST /api/responses/submit?token=...` | No login — body `{"responses": [{"server_id", "decision", "comment"}, ...]}`, one entry per server the token covers |
| `GET /api/my/servers` | Any logged-in account — servers where `owner_email` matches your account email |
| `POST /api/my/servers/{id}/respond` | Any logged-in account — must own that server (or be staff) |
| `GET /api/dashboard/kpis` | Admin only. Aggregated KPIs + chart data |

All admin/owner routes above (everything except `/auth/login` and the token-based
`/responses/*`) expect header `Authorization: Token <key>`, obtained from `/auth/login`.

## If something breaks

1. **Blank page / 404s on CSS or JS** — you likely skipped `npm run build`, or it landed somewhere other than `static/react/`. Check that `static/react/index.js` exists.
2. **"Admin login required" errors right after upgrading** — the old shared `ADMIN_API_KEY` is retired; you need a real account now (`createsuperuser` or `/admin/`) and to log in through the UI.
3. A pinned package version in `requirements.txt` that's since changed — try relaxing the pin.
4. Docker Desktop not fully started before `docker compose up` — give it a minute.
5. Port conflicts (8000, 5173, 5432, 6379 need to be free).

Tell me the exact error and I'll fix it directly.
