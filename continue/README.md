# Continue extension — use this proxy

This folder is the **team template**: copy [`project-llm.yaml`](project-llm.yaml) into your **personal** Continue config (`~/.continue/config.yaml` on macOS/Linux). The git repo does **not** include a project `.continue/` directory — that path is only for your machine if Continue creates it.

The backend accepts your **project key** as **`Authorization: Bearer …`**, which matches Continue’s **`apiKey`** field when **`provider: openai`**.

## 0. Pre-flight (before Continue)

1. **Microsoft SQL Server** is reachable and `DATABASE_URL` in `backend/.env` is correct; schema applied (`backend/sql/schema.sql`).
2. **`OPENAI_API_KEY`** is set in `backend/.env` ([OpenAI API keys](https://platform.openai.com/api-keys)).
3. **Backend is up:** from `backend/`, `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
4. Quick check: `curl -s http://127.0.0.1:8000/health` → `{"status":"ok"}`.

## 1. Create a project key

With the API running, call admin (or use your own tooling):

```bash
curl -sS -X POST http://127.0.0.1:8000/admin/create-key \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: YOUR_ADMIN_API_KEY" \
  -d '{"name":"Continue laptop"}'
```

Copy the returned **`key`** (`sk_proj_…`).

## 2. Add the model to Continue

**Option A — merge into global config**

1. Open Continue → config (gear / “Local Config”), or edit:
   - **macOS/Linux:** `~/.continue/config.yaml`
   - **Windows:** `%USERPROFILE%\.continue\config.yaml`
2. Under `models:`, add the block from [`project-llm.yaml`](project-llm.yaml) (or merge the whole file if you use it as a standalone profile where your Continue version supports that).

**Option B — workspace profile (if your Continue build supports `.continue/configs/`)**

Copy `project-llm.yaml` into:

`.continue/configs/project-llm.yaml`

in your home directory or project (per [Continue configuration](https://docs.continue.dev/customize/deep-dives/configuration)).

## 3. Replace placeholders

| Placeholder | Set to |
|-------------|--------|
| `apiBase` | Your backend origin + `/v1`, e.g. `https://your-api.azurewebsites.net/v1` |
| `apiKey` | The full **`sk_proj_…`** string from create-key |

## 4. Select the model in Continue

In the chat model dropdown, pick **“GPT-5 (project proxy)”** (or whatever `name` you used).

## Notes

- **`model`** must be an id your **OpenAI** key can call (e.g. `gpt-5`); the proxy forwards the request body to OpenAI.
- For **`gpt-5`** with a **custom `apiBase`** (this proxy), add **`useResponsesApi: false`** on that model. Otherwise Continue calls **`/v1/responses`**, which this app does not implement — you get **`{"detail":"Not Found"}`**. See [Continue — OpenAI](https://docs.continue.dev/customize/model-providers/top-level/openai) (“Disable the Responses API”).
- Use **`apiBase` without a trailing slash**, e.g. `http://127.0.0.1:8000/v1` (not `.../v1/`). If **`ENABLE_HMAC_CHECK`** is on, point at **`hmac-proxy`** instead (e.g. `http://127.0.0.1:8001/v1`) so Continue does not need to send HMAC headers.
- The proxy uses a **non-stream** upstream call for stability, then may return an SSE-shaped response when clients request streaming; usage is logged from the upstream **`usage`** field.
- Official OpenAI provider docs: [Continue — OpenAI](https://docs.continue.dev/customize/model-providers/top-level/openai).
