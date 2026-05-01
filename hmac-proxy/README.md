# HMAC signing gateway

Small service that sits **in front of** the FastAPI backend. Your IDE (Continue) or any HTTP client sends `Authorization: Bearer sk_proj_…` **only**; the gateway adds `x-signature`, `x-timestamp`, and `x-nonce` using the same algorithm as `backend/app/middleware/project_key.py`, then forwards the body to the real backend.

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `BACKEND_URL` | No | Default `http://127.0.0.1:8000` (no trailing slash). |
| `HMAC_SIGNING_SECRET` | **Yes** | Must match backend `HMAC_SIGNING_SECRET`. |
| `CORS_ORIGINS` | No | Default `*`. Comma-separated list if you need credentials + explicit origins. |

## Run locally

```powershell
cd hmac-proxy
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:HMAC_SIGNING_SECRET="same-as-backend-.env"
$env:BACKEND_URL="http://127.0.0.1:8000"
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001
```

Backend must have `ENABLE_HMAC_CHECK=true` and the same `HMAC_SIGNING_SECRET`.

## Continue

Point at the gateway (not the backend):

- `apiBase: http://127.0.0.1:8001/v1`
- `apiKey: sk_proj_…`
- `useResponsesApi: false`

## How hard is it to test?

**Easy** — one `Invoke-RestMethod` or `curl` to the gateway on port **8001** with your real project key (no HMAC headers). If the backend is up, HMAC is on, and secrets match, you get a normal completion JSON (or the same error the backend would return for bad model/key).

If something fails:

- **401 missing HMAC** on **8000** — you hit the backend directly; use **8001**.
- **401 missing HMAC** on **8001** — proxy env missing `HMAC_SIGNING_SECRET` or typo.
- **401 invalid signature** on **8001** — proxy and backend `HMAC_SIGNING_SECRET` differ, or body altered before sign (unlikely with this proxy).

## Note on streaming

This gateway uses a buffered `POST` to the backend (full response in memory). That matches how this repo’s backend often handles streaming upstream. For very large streamed responses, consider extending the gateway to stream with `httpx` `stream=True` later.
