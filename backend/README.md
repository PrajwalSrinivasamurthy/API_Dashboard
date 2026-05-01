# Project LLM — Backend

FastAPI service: **`x-project-key`** on `POST /v1/chat/completions` → **OpenAI** Chat Completions API, usage + cost in PostgreSQL, admin APIs.

## Setup

1. PostgreSQL: create DB and apply schema:

```bash
createdb project_llm
psql "postgresql://USER:PASS@localhost:5432/project_llm" -f sql/schema.sql
```

If the database already existed before dashboard auth was added, apply **`sql/migration_dashboard_users.sql`** once (creates **`dashboard_users`**; safe to re-run).

2. Python 3.9+:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` (see `.env.example` for patterns):

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Async Postgres URL; must use driver **`postgresql+asyncpg://`** (or plain `postgresql://` — the app rewrites it). Examples for local, macOS, and Azure are in `.env.example`. |
| `OPENAI_API_KEY` | Key from [OpenAI API keys](https://platform.openai.com/api-keys). |
| `OPENAI_BASE_URL` | Optional. Default **`https://api.openai.com/v1`**. The proxy calls `{OPENAI_BASE_URL}/chat/completions`. Use a different base only for OpenAI-compatible proxies. |
| `ADMIN_API_KEY` | Secret for `/admin/*` routes. |
| `JWT_SECRET` | Shared with the Next.js app: signs dashboard session JWTs (use a long random string, ≥32 bytes recommended). |
| `JWT_EXPIRE_HOURS` | Optional. Default **168** (7 days). |

3. Run:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API

| Method | Path | Auth |
|--------|------|------|
| POST | `/v1/chat/completions` | `x-project-key` (or `Authorization: Bearer`) |
| POST | `/auth/login` | Body `{"email":"…","password":"…"}` — email must exist in `dashboard_users` |
| POST | `/auth/change-password` | `Authorization: Bearer <dashboard JWT>` body `{"old_password":"…","new_password":"…"}` (new password min 8 chars) |
| GET | `/admin/project-keys` | `X-Admin-Key` |
| POST | `/admin/create-key` | `X-Admin-Key` body `{"name":"…"}` |
| POST | `/admin/disable-key` | `X-Admin-Key` body `{"id":1}` or `{"key":"…"}` |
| POST | `/admin/dashboard-users` | `X-Admin-Key` body `{"email":"…"}` optional `"password"` (default **`password`**) — whitelists a dashboard login |
| GET | `/admin/dashboard-users` | `X-Admin-Key` — list whitelisted users (**id**, **email**, timestamps only; passwords are bcrypt hashes and are never returned) |
| POST | `/admin/delete-dashboard-user` | `X-Admin-Key` body `{"id":1}` or `{"email":"…"}` |
| POST | `/admin/update-dashboard-user-password` | `X-Admin-Key` body `{"id":1,"new_password":"…"}` or `{"email":"…","new_password":"…"}` (**new_password** min 8 chars) |
| GET | `/admin/usage` | `X-Admin-Key` |

**Dashboard whitelist:** Table **`dashboard_users`** (`email`, bcrypt **`password_hash`**). There is no public signup; add rows via **`POST /admin/dashboard-users`** or SQL after hashing a password in Python (`app/services/passwords.py`).

**Security:** `OPENAI_API_KEY` is never returned to clients. Usage is logged from the **non-stream** upstream response (see `app/routers/proxy.py`).

## `app/` package layout

Python package root for the FastAPI app. Imports use the `app.` prefix (e.g. `from app.config import get_settings`).

| File / folder | Role |
|---------------|------|
| `__init__.py` | Marks `app` as a package. |
| **`main.py`** | App entry: loads `backend/.env`, builds `FastAPI`, adds CORS + project-key middleware, mounts routers (`/v1`, `/admin`), `/health`, validation error handler. **`lifespan`** disposes the DB engine on shutdown. |
| **`config.py`** | **`Settings`**: typed env (`DATABASE_URL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `ADMIN_API_KEY`, `JWT_SECRET`, `JWT_EXPIRE_HOURS`, `CORS_ORIGINS`, `PRICING_JSON`). **`get_settings()`** is cached. **`ensure_async_driver`** rewrites `postgresql://` → `postgresql+asyncpg://` for SQLAlchemy async. **`parse_pricing_json`** parses `PRICING_JSON` into per-model USD rates. |
| **`database.py`** | **`Base`**: SQLAlchemy declarative base. **`engine`** / **`async_session_factory`**: async Postgres. **`get_db`**: FastAPI dependency that yields a session and **commits** on success, **rolls back** on error. |
| **`models.py`** | ORM: **`ProjectKey`**, **`UsageLog`**, **`DashboardUser`** (`dashboard_users`: whitelisted emails + bcrypt password hash). |
| **`schemas.py`** | Pydantic models for admin JSON: create/disable key, list keys, **`AdminUsageResponse`** / **`UsagePerProject`**, etc. Separates API shape from ORM. |
| **`deps.py`** | **`require_admin`**: validates header **`X-Admin-Key`** vs `ADMIN_API_KEY` (used by `/admin/*`). **`get_project_key_id_from_middleware`**: reads `request.state.project_key_id` set by middleware for `/v1/chat/completions`. |
| **`middleware/project_key.py`** | **`_extract_project_key`**: reads `x-project-key` or `Authorization: Bearer`. **`ProjectKeyValidationMiddleware`**: for **`POST /v1/chat/completions` only**, loads active key from DB, sets **`request.state.project_key_id`** (and name); otherwise returns 401 JSON. |
| **`routers/proxy.py`** | **`POST /v1/chat/completions`**: forwards body to OpenAI **`…/chat/completions`** with server `OPENAI_API_KEY`. If client asked for **`stream: true`**, forces non-stream upstream for stability, then returns either a normal JSON response or a **small SSE** (`text/event-stream`) so IDE clients still see a stream-shaped reply. Logs **`UsageLog`** + updates **`used_tokens`** from response **`usage`**. **`_normalize_upstream_error`**: normalizes upstream errors into `{ "error": … }`. **`_as_sse_line`**: SSE framing. |
| **`routers/auth.py`** | **`/auth/login`**, **`/auth/change-password`** — whitelist check against **`dashboard_users`**, JWT issuance. |
| **`routers/admin.py`** | **`/admin/project-keys`**, **`/admin/create-key`**, **`/admin/disable-key`**, **`/admin/usage`**, **`/admin/dashboard-users`** — all require **`require_admin`**. **`_new_key`** generates `sk_proj_…` keys. |
| **`services/passwords.py`** | Bcrypt hash / verify for dashboard passwords. |
| **`services/dashboard_jwt.py`** | HS256 JWT create/decode for dashboard sessions. |
| **`services/pricing.py`** | **`estimate_cost_usd`**: uses `PRICING_JSON` (per model, USD per 1M prompt/completion tokens); falls back to **`gpt-5`** / **`gpt-4o`** defaults if model unknown. |

### Key functions (quick reference)

- **`main.py`**: `_cors()` — parses `CORS_ORIGINS` (`*` vs comma list); `health()` — liveness; `validation_exc()` — 422 JSON for bad bodies.
- **`config.py`**: `get_settings()`, `parse_pricing_json(raw)`.
- **`database.py`**: `get_db()`.
- **`deps.py`**: `require_admin(...)`, `get_project_key_id_from_middleware(request)`.
- **`middleware/project_key.py`**: `_extract_project_key(request)`, `ProjectKeyValidationMiddleware.dispatch`.
- **`routers/proxy.py`**: `_normalize_upstream_error`, `_as_sse_line`, `chat_completions`.
- **`routers/admin.py`**: `_new_key`, `list_project_keys`, `create_key`, `disable_key`, `admin_usage`.
- **`services/pricing.py`**: `estimate_cost_usd(model, prompt_tokens, completion_tokens)`.

## Pricing

Override with `PRICING_JSON` in `.env` (USD per 1M prompt/completion tokens per model id). Align with [OpenAI pricing](https://openai.com/api/pricing/); defaults in `app/config.py` are illustrative.

## Continue (IDE)

Example **`config.yaml`** snippet: [continue/project-llm.yaml](../continue/project-llm.yaml) — setup steps: [continue/README.md](../continue/README.md).
