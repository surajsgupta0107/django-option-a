# Server Utilization Portal — Frontend

React + Vite app, wired to this project's Django backend via `fetch`. Two ways to run it:

## Option A — build it, let Django serve it (recommended default)

```bash
npm install
npm run build
```

Outputs straight into `../static/react/` (not the usual `dist/` — see `vite.config.js`).
Then just run the Django backend (`python manage.py runserver` or `docker compose up`)
and visit `http://localhost:8000/`. One process, one port, done. See the project root
README for the full setup.

## Option C — Vite dev server (hot reload, for active frontend development)

```bash
npm install
npm run dev
```

Visit `http://localhost:5173`. The app's default API base URL is the relative path
`/api` (correct once Django serves the build, per Option A above) — running the dev
server instead means the frontend and API are on different ports (5173 vs 8000), so
`vite.config.js` proxies `/api/*` requests from the dev server through to
`http://localhost:8000` automatically. No manual config needed; just make sure the
Django backend is actually running on port 8000 first.

> **Note on testing:** built in a sandbox without outbound network access, so
> `npm install` hasn't actually been run here. The component was syntax/bundle-checked
> with esbuild against its real import surface (React, recharts, lucide-react), and the
> Vite config was checked the same way, but please run it for real and report back
> anything that doesn't come up clean.

## Pointing it at a different backend

Go to **Settings → API connection** in the app itself to override the API base URL and
admin key at runtime — saved to `localStorage`, so it persists across reloads. Useful
if you're running the backend somewhere other than `localhost:8000`.

## What changed from the original chat-artifact prototype

- All server data, thresholds, reminders, and owner responses are fetched from and
  written to the backend — nothing is generated or mutated client-side anymore.
- File upload sends the raw CSV/XLSX to `POST /api/servers/upload`; the backend does
  the column-mapping and parsing (same flexible-matching logic, just server-side now).
- CSV export of the current filtered view is still done client-side for simplicity —
  it exports whatever's currently loaded and filtered.
- The Owner Portal tab uses the backend's dev-mode lookup/submit routes
  (`/api/responses/by-server-id/{id}`, `/api/responses/submit-dev/{id}`) so it can keep
  the same "pick your server from a dropdown" flow without wiring up email-link routing
  in this SPA. The *real* reminder-email flow still uses signed tokenized links
  (`/api/responses/lookup?token=...`, `/api/responses/submit?token=...`) — building a
  proper `/owner-response?token=...` route for those is a reasonable next step once you
  decide on real owner-facing hosting.
