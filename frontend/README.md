# Project LLM — Next.js dashboard

Admin UI for **project keys** and **usage** (maps to `project_keys` and aggregated `usage_logs` from the FastAPI backend).

## How it works

- **`/dashboard`** and **`/api/admin/*`** require a signed-in session: **`middleware.ts`** checks an **httpOnly** cookie set by **`POST /api/auth/login`** (JWT from FastAPI **`POST /auth/login`**). **`JWT_SECRET`** in `.env.local` must match the backend.
- Browser calls **same-origin** routes under `/api/admin/*`.
- Next.js **Route Handlers** forward requests to FastAPI with **`X-Admin-Key`** from env.
- **`ADMIN_API_KEY` and `JWT_SECRET` never ship to the client** — keep them only in `.env.local` / hosting app settings.

## Setup

```bash
cd frontend
npm install
```

Create **`frontend/.env.local`** with at least: `BACKEND_URL`, `ADMIN_API_KEY`, **`JWT_SECRET`** (same value as backend `JWT_SECRET`), and optionally **`JWT_EXPIRE_HOURS`** (default **5**, must match backend for login cookie lifetime).

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) — you are redirected to **`/login`**, then **`/dashboard`** after a successful sign-in. Whitelist emails in the backend **`dashboard_users`** table (e.g. **`POST /admin/dashboard-users`** with **`X-Admin-Key`**).

From the repo root you can run **`npm run dev:frontend`** instead of `cd frontend` + `npm run dev`.

## Styling looks “broken” (plain white / Times font)

1. **Run the dev server from the `frontend` folder** (or from repo root: `npm run dev:frontend`).
2. **Hard refresh** the browser (Cmd+Shift+R / Ctrl+Shift+R).
3. In DevTools → **Network**, confirm `/_next/static/css/*.css` returns **200** (not blocked).
4. If needed, delete `frontend/.next` and run `npm run dev` again.

## Tabs

| Tab | Backend |
|-----|---------|
| **Usage overview** | `GET /admin/usage` — totals + per-project table |
| **Project keys** | `GET /admin/project-keys` — table + disable → `POST /admin/disable-key` |
| **Virtual key** | `POST /admin/create-key` — returns a **one-time share link** (`/vk/…`); recipient opens it once to copy the key |

## Production

```bash
npm run build
npm start
```

Set `BACKEND_URL`, `ADMIN_API_KEY`, and `JWT_SECRET` in the host environment (e.g. Azure App Service application settings).
