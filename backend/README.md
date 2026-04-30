# Project LLM — Backend

FastAPI service: **`x-project-key`** on `POST /v1/chat/completions` → **OpenAI** Chat Completions API, usage + cost in **Microsoft SQL Server**, admin APIs.

## Setup

### Quick Docker local stack (backend + frontend + SQL Server)

From repo root:

```bash
docker compose up --build
```

Then:

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend health: [http://localhost:8000/health](http://localhost:8000/health)

Before first real use, run `sql/schema.sql` against the SQL Server container (`127.0.0.1:1433`) using Azure Data Studio / SQL extension, or `sqlcmd`.

Common env overrides in **repo root** `.env` (Compose reads this file automatically):

- `OPENAI_API_KEY`
- `ADMIN_API_KEY`
- `JWT_SECRET`
- **`DATABASE_URL`** — optional. Full `mssql+aioodbc://…` string to use a **remote** SQL Server (SSMS / Azure). If **unset**, Compose defaults to the bundled **`sqlserver`** container on `sqlserver:1433` using `MSSQL_*` below.
- `MSSQL_SA_PASSWORD` and `MSSQL_SA_PASSWORD_URLENC` (only affect the default URL when `DATABASE_URL` is unset)
- `MSSQL_DB_NAME` (defaults to `master`)

**Native `uvicorn` (no Docker):** set `DATABASE_URL` in **`backend/.env`** (see **`.env.example`**).

### Native (non-Docker) setup

1. **SQL Server** (SSMS / Azure SQL / on-prem): create an empty database, then run the T-SQL script:

- Open **`sql/schema.sql`** in **SQL Server Management Studio**, connect to your server, select the target database, and execute the script (or use **`sqlcmd`** with `-d YourDatabase -i sql/schema.sql`).

**macOS:** Microsoft does not ship a native “SQL Server.app” for Mac. Use **Docker** to run the engine locally: from the **repo root**, run **`docker compose up -d`** (see root **`docker-compose.yml`**; default `sa` password is in that file — change it for anything beyond local dev). On Apple Silicon, Docker may pull the **linux/amd64** image (emulation); that is normal.

Use a **Cursor / VS Code extension** only as a **client** (e.g. Microsoft’s **SQL Server (mssql)** or **Azure Data Studio**) to connect to `127.0.0.1,1433`, create a database, and execute **`sql/schema.sql`**. Extensions do **not** replace the server; they talk to SQL Server in Docker (or Azure).

Install the **ODBC Driver 18 for SQL Server** on the Mac that runs **Python** ([install on macOS](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/install-microsoft-odbc-driver-sql-server-macos)). You typically need **unixODBC** as well (`brew install unixodbc`).

If the database already existed before **`dashboard_users`** was added, run **`sql/migration_dashboard_users.sql`** once (idempotent).

If **`project_key_reveals`** is missing (virtual-key share links), run **`sql/migration_project_key_reveals.sql`** once (idempotent).

If **`project_keys.allowed_client_ip`** is missing (IP lock after reveal), run **`sql/migration_project_key_allowed_ip.sql`** once (idempotent).

If **`budget_usd`**, **`budget_warn_sent`**, or **`project_key_security_events`** is missing, run **`sql/migration_budget_spike_security.sql`** once (idempotent).

If **`hmac_nonces`** is missing (HMAC replay protection), run **`sql/migration_hmac_nonces.sql`** once (idempotent).

**Virtual key + IP:** When someone opens **`GET /public/vk/{token}`**, the server stores their client IP on that **`project_keys`** row. After that, **`POST /v1/chat/completions`** with that key only succeeds from the **same IP** (see `X-Forwarded-For` / `CF-Connecting-IP` / `X-Real-IP` / TCP peer). Open the reveal link through the **same Next.js host** you use in production so the real browser IP is forwarded. Keys with **`allowed_client_ip` NULL** (e.g. old rows) are not IP-restricted until a reveal runs.

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
| `DATABASE_URL` | Async SQL Server URL: **`mssql+aioodbc://…`** (plain `mssql://` is rewritten). Must include a **`driver=`** query param (see **`.env.example`**). URL-encode characters such as **`@`** in passwords. |
| `OPENAI_API_KEY` | Key from [OpenAI API keys](https://platform.openai.com/api-keys). |
| `OPENAI_BASE_URL` | Optional. Default **`https://api.openai.com/v1`**. The proxy calls `{OPENAI_BASE_URL}/chat/completions`. Use a different base only for OpenAI-compatible proxies. |
| `ADMIN_API_KEY` | Secret for `/admin/*` routes. |
| `JWT_SECRET` | Shared with the Next.js app: signs dashboard session JWTs (use a long random string, ≥32 bytes recommended). |
| `JWT_EXPIRE_HOURS` | Optional. Default **5** (hours). Same TTL is used for **virtual-key reveal** links after create. |
| `TEAMS_WEBHOOK_URL` | Optional. **Microsoft Teams** Incoming Webhook — posts when a bound key is used from a **different IP**, and when cumulative spend crosses **`BUDGET_THRESHOLD_FRACTION`** of **`budget_usd`**. |
| `ENABLE_IP_CHECK` | Optional. Default **false**. If true, enforce `allowed_client_ip` lock for project keys. |
| `ENABLE_HMAC_CHECK` | Optional. Default **true**. Require signed requests with `x-signature`, `x-timestamp`, and `x-nonce`. |
| `HMAC_SIGNING_SECRET` | Required when HMAC check is enabled. Shared secret used with project key to verify request signatures. |
| `HMAC_MAX_SKEW_SECONDS` | Optional. Default **300**. Max allowed timestamp skew for signed requests. |
| `HMAC_NONCE_TTL_SECONDS` | Optional. Default **600**. Replay-protection nonce lifetime. |
| `SPIKE_WINDOW_SECONDS` | Optional. Default **60**. Rolling window for spike checks. |
| `SPIKE_MAX_COST_USD` | Optional. Default **5**. Max summed **`usage_logs.cost`** in the window (plus a conservative estimate for the current request). |
| `SPIKE_MAX_TOKENS` | Optional. Default **500000**. Max summed tokens in the window (plus estimate). |
| `SPIKE_MAX_REQUESTS` | Optional. Default **120**. Max completion calls in the window. |
| `BUDGET_THRESHOLD_FRACTION` | Optional. Default **0.8**. One-time Teams + DB event when spend reaches this fraction of **`budget_usd`** (per key). |
| `LOG_TO_FILES` | Optional. Default **true**. If **false**, logs go to stdout only (no rotation files). |
| `LOG_DIR` | Optional. Default **`logs`** (folder under **`backend/`**). |
| `DEV_LOG_FILE` / `AUDIT_LOG_FILE` | Optional. Defaults **`dev.log`** and **`audit.log`**. |
| `LOG_LEVEL` | Optional. Default **INFO**; use **DEBUG** for more developer detail under the **`app`** logger. |
| `LOG_ENCRYPTION_KEY` | Optional. **Fernet** key (url-safe base64). If set, encrypts on-disk log files per **`LOG_ENCRYPT_*`** (invalid key → startup error). |
| `LOG_ENCRYPT_AUDIT` | Optional. Default **true** when encryption is used — encrypt **`audit.log`**. |
| `LOG_ENCRYPT_DEV` | Optional. Default **false** — set **true** to encrypt **`dev.log`** on disk too. |

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
| POST | `/admin/create-key` | `X-Admin-Key` body `{"name":"…"}` — returns **`reveal_token`** + **`reveal_expires_at`** (no raw key); share **`GET /public/vk/{token}`** via your app’s `/vk/…` page |
| GET | `/public/vk/{token}` | **No auth** — returns **`{"key":"sk_proj_…"}`** once, then invalidates the token (404 if used, expired, or unknown) |
| POST | `/admin/disable-key` | `X-Admin-Key` body `{"id":1}` or `{"key":"…"}` |
| POST | `/admin/dashboard-users` | `X-Admin-Key` body `{"email":"…"}` optional `"password"` (default **`password`**) — whitelists a dashboard login |
| GET | `/admin/dashboard-users` | `X-Admin-Key` — list whitelisted users (**id**, **email**, timestamps only; passwords are bcrypt hashes and are never returned) |
| POST | `/admin/delete-dashboard-user` | `X-Admin-Key` body `{"id":1}` or `{"email":"…"}` |
| POST | `/admin/update-dashboard-user-password` | `X-Admin-Key` body `{"id":1,"new_password":"…"}` or `{"email":"…","new_password":"…"}` (**new_password** min 8 chars) |
| GET | `/admin/usage` | `X-Admin-Key` |

**Dashboard whitelist:** Table **`dashboard_users`** (`email`, bcrypt **`password_hash`**). There is no public signup; add rows via **`POST /admin/dashboard-users`** or SQL after hashing a password in Python (`app/services/passwords.py`).

**Security:** `OPENAI_API_KEY` is never returned to clients. Usage is logged from the **non-stream** upstream response (see `app/routers/proxy.py`). Each key has a **`budget_usd`** (default **$25**), **spike limits** over a rolling window, and **`project_key_security_events`** rows for **ip_mismatch**, **hmac_signature_invalid**, **hmac_replay_blocked**, **budget_blocked**, **spike_blocked**, and **budget_threshold**.  
When `ENABLE_HMAC_CHECK=true`, sign each request with:
- `x-timestamp`: unix epoch seconds
- `x-nonce`: unique random string (single-use within TTL)
- `x-signature`: `hex(hmac_sha256((HMAC_SIGNING_SECRET + ":" + project_key), METHOD + "\n" + PATH + "\n" + TIMESTAMP + "\n" + NONCE + "\n" + sha256(raw_body_bytes).hexdigest()))`

**Logs:** With default settings, **`backend/logs/dev.log`** receives application logs (developers: set **`LOG_LEVEL=DEBUG`**). **`backend/logs/audit.log`** receives one **JSON object per line** for IT: **`admin.http`** (every `/admin/*` request with status and duration), **`dashboard.login`** / **`dashboard.change_password`**, **`vk.reveal`**, **`proxy.*`** security/limit events (no API keys or raw project keys). Configure via **`LOG_DIR`**, **`LOG_TO_FILES`**, etc. (see **`.env.example`**).

**Encrypting log files (optional):** Set **`LOG_ENCRYPTION_KEY`** to a **Fernet** key (generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`). By default only **`audit.log`** is encrypted on disk (**`LOG_ENCRYPT_AUDIT=true`**, **`LOG_ENCRYPT_DEV=false`**); set **`LOG_ENCRYPT_DEV=true`** to encrypt **`dev.log`** too. **Stdout/stderr stay plaintext** so operators can still `docker logs` without the key. Decrypt a file: **`python scripts/decrypt_log_file.py logs/audit.log`** with **`LOG_ENCRYPTION_KEY`** in the environment (or **`--key-file`**). The key in **`.env`** protects against disk theft only if the secret is stored separately (e.g. vault, KMS-injected env); for many deployments **full-disk encryption** (BitLocker, LUKS, encrypted cloud volumes) or **shipping logs to a SIEM over TLS** is simpler than app-level crypto.

## `app/` package layout

Python package root for the FastAPI app. Imports use the `app.` prefix (e.g. `from app.config import get_settings`).

| File / folder | Role |
|---------------|------|
| `__init__.py` | Marks `app` as a package. |
| **`main.py`** | App entry: loads `backend/.env`, builds `FastAPI`, adds CORS + project-key middleware, mounts routers (`/v1`, `/admin`), `/health`, validation error handler. **`lifespan`** disposes the DB engine on shutdown. |
| **`config.py`** | **`Settings`**: typed env (`DATABASE_URL`, `OPENAI_*`, `ADMIN_API_KEY`, `JWT_*`, `CORS_ORIGINS`, `PRICING_JSON`, optional **`TEAMS_WEBHOOK_URL`**, **spike** / **budget threshold** knobs). **`get_settings()`** is cached. **`ensure_async_mssql`** normalizes `mssql://` / `sqlserver://` → **`mssql+aioodbc://`**. PostgreSQL URLs are rejected. **`parse_pricing_json`** parses `PRICING_JSON` into per-model USD rates. |
| **`database.py`** | **`Base`**: SQLAlchemy declarative base. **`engine`** / **`async_session_factory`**: async SQL Server (**aioodbc**). **`get_db`**: FastAPI dependency that yields a session and **commits** on success, **rolls back** on error. |
| **`models.py`** | ORM: **`ProjectKey`** (includes **`budget_usd`**, **`budget_warn_sent`**), **`UsageLog`**, **`DashboardUser`**, **`ProjectKeyReveal`**, **`ProjectKeySecurityEvent`**. |
| **`schemas.py`** | Pydantic models for admin JSON: create/disable key, list keys, **`AdminUsageResponse`** / **`UsagePerProject`**, etc. Separates API shape from ORM. |
| **`deps.py`** | **`require_admin`**: validates header **`X-Admin-Key`** vs `ADMIN_API_KEY` (used by `/admin/*`). **`get_project_key_id_from_middleware`**: reads `request.state.project_key_id` set by middleware for `/v1/chat/completions`. |
| **`middleware/project_key.py`** | **`_extract_project_key`**: reads `x-project-key` or `Authorization: Bearer`. **`ProjectKeyValidationMiddleware`**: for **`POST /v1/chat/completions` only**, loads active key from DB, enforces **`allowed_client_ip`**, logs **`ip_mismatch`** + optional **Teams** message, sets **`request.state.project_key_id`** (and name); otherwise returns 401/403 JSON. |
| **`routers/proxy.py`** | **`POST /v1/chat/completions`**: **budget** + **spike** gates (before upstream); forwards to OpenAI with server key. If **`stream: true`**, forces non-stream upstream, then returns JSON or a short **SSE** for IDE clients. Logs **`UsageLog`**, updates **`used_tokens`**; **`budget_threshold`** + Teams once. **`_normalize_upstream_error`**, **`_as_sse_line`**. |
| **`services/usage_limits.py`** | **`total_spent_usd`**, **`window_usage_stats`**, conservative cost/token upper bounds for gating. |
| **`services/teams_webhook.py`** | **`post_teams_text`**: optional **`TEAMS_WEBHOOK_URL`** POST. |
| **`logging_config.py`** | **`configure_logging()`**: rotating **`dev.log`** + **`audit.log`** under **`LOG_DIR`**; optional **Fernet** encryption via **`LOG_ENCRYPTION_KEY`**. |
| **`fernet_rotating_file_handler.py`** | **`FernetRotatingFileHandler`**: one ciphertext line per log record when encryption is enabled. |
| **`services/audit_log.py`** | **`log_audit(...)`**: JSON lines to **`app.audit`** (IT file). |
| **`middleware/audit_http.py`** | **`AuditHttpMiddleware`**: records each completed **`/admin/*`** HTTP call (method, path, status, client IP, duration). |
| **`routers/auth.py`** | **`/auth/login`**, **`/auth/change-password`** — whitelist check against **`dashboard_users`**, JWT issuance. |
| **`routers/reveal.py`** | **`GET /public/vk/{token}`** — one-time reveal of a **`project_keys`** secret (no auth). |
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
