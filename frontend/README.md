# Frontend — API Performance Analytics Dashboard

Zero-build single-page dashboard. Three files: `index.html`, `style.css`,
`app.js`. Talks to the Gateway on `http://localhost:8080` via fetch and
stores the JWT in `sessionStorage`.

## Serve locally

Any static server works. Simplest:

```bash
cd frontend
python3 -m http.server 5173
# open http://localhost:5173
```

Default credentials for the local admin user (seeded by `V5__seed_admin_user.sql`):

- username: `admin`
- password: `admin1234!`

## Tiles

- **Service health** — composite health score + status per service (from
  `GET /dashboard/health`, which fans out to Analytics + ML).
- **Traffic** — current RPM vs 60-min forecast (`GET /dashboard/traffic`).
- **Latency** — mean / P95 / P99 per service.
- **Predictions** — anomaly score + failure probability + risk label.
- **Open alerts** — from Analytics, enriched with the ML-assigned priority.

The Gateway URL is editable in the footer; the JWT and URL persist across
page reloads via `sessionStorage`.
