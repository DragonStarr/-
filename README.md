# Оператор дня

Autonomous Telegram bot + Next.js Mini App/PWA for WB/Ozon/Yandex Market sellers and PVZ owners.

What is included now:

- FastAPI service with health, task, action, feedback and Telegram webhook endpoints.
- aiogram bot text/keyboards for button-first Telegram testing.
- Telegram account buttons for checking a cabinet and updating data without typed commands.
- Isolated ReplayHub for tests; API, Telegram and Mini App use tenant DB/imported data and do not substitute fake seller tasks when sources are empty.
- 23 module contracts following the living TZ/notebook: 22 action modules plus the morning orchestrator.
- Seller context from verified Telegram Mini App `initData` or short-lived bearer session tokens; raw context headers are local/test only.
- Account connection endpoints encrypt tokens and return capability status without exposing secrets.
- Owner-only account validation endpoint checks a safe read operation before the account is treated as live-ready; Ozon, WB and Yandex Market dry-run plans are supported.
- Idempotent task confirmation through `X-Idempotency-Key`, audit log and token usage tracking.
- LLM router for FreeModel/OpenAI-compatible API with strict budget fallback and redaction.
- Owner-only architecture review endpoint uses the same LLM router to check the LK/API -> server -> DB -> bot tree.
- Owner-only architecture gate endpoint exposes the machine-readable LK/API -> transport -> workers -> DB -> orchestrator -> Telegram topology; local LLM is the primary reviewer, external OpenAI-compatible providers are optional and disabled unless explicitly enabled in env.
- Next.js 16 Mini App/PWA with Telegram-style bottom navigation, plain Russian labels, lime/M-stripe visual language and API rewrites to the backend.
- Celery morning collection task with retry/backoff and saved ranked tasks.
- Optional embedded morning scheduler for one-server pilots; it refreshes the local task queue from connected/manual data without marketplace writes.
- Marketplace transport layer with operation catalog, platform host routing, path parameters, safe dry-run, safety gates, retry on 429/5xx and Ozon last_id pagination.
- Local vendored marketplace SDK payload builders in `vendor/marketplace_sdk`, so review, price and bid write plans do not depend on GitHub repositories at runtime.
- Catalog sync endpoint and Celery task for Ozon/WB/Yandex Market; secrets are decrypted only inside the service and never returned.
- Synced catalog rows are saved to `products` with stock, rating, commission and raw source payload where the marketplace provides them; API and Telegram morning tasks read tenant DB data and return setup/empty states when sources are missing.
- Manual catalog import endpoint for pilot sellers when a marketplace API is unavailable or a test account needs seed products.
- Sales import endpoint feeds demand forecasts from real order/sale history instead of only price/rating heuristics.
- Review import endpoint for pilot sellers; the morning bot reads tenant reviews/questions from DB and keeps risky negative cases human-only.
- Source-linked claim deadline policies, so WB/Ozon/YM claim windows are not hardcoded guesses.
- Claim candidate import endpoint; the morning bot builds reimbursement tasks from tenant DB data and marks deadlines as verified only when a source-linked policy exists.
- PVZ point/staff import endpoint; the morning bot builds 2/2 schedules and payroll from tenant DB data instead of static employees.
- Operational data import endpoint for rules, accounting, studio requests, incidents, eval runs and source changes; tail modules M12/M14/M15/M16/M17/M18 read tenant DB rows and write durable result artifacts.
- Tenant-scoped semantic memory API stores seller rules, notes and decisions with sanitized text, local vectors and a Postgres pgvector/HNSW-ready schema.
- Tenant-scoped memory can call an OpenAI-compatible/BGE-M3 embedding endpoint from env and falls back to deterministic local vectors when the endpoint is unavailable.
- Confirmed actions now carry a durable lifecycle checkpoint with collected, confirmed, marketplace planned/executed or human escalation, audit and rollback hints.
- Self-update control plane snapshots upstream references, runs real sandbox checks, LLM review, canary gates and rollback to last-known-good.
- Operator capability catalog: 30+ skills/plugins on every action and 10 required MCP-style checks in every action payload.
- SQLAlchemy schema and Alembic migration skeleton for Postgres + pgvector-ready tenant isolation, including ads, claims, niches, content, semantic memory and account guard data.

Local start:

```powershell
uv sync
uv run pytest
uv run uvicorn operator_day.main:create_app --factory --host 0.0.0.0 --port 8000
cd apps/miniapp
npm ci
npm run build
npm run dev
```

No real secrets belong in the repository. Put them in `.env`, never in code or docs.
For Yandex Market accounts, pass `campaignId` when connecting the account so validation can build the safe read probe.

Pilot API examples:

- `GET /api/tasks/morning`
- `GET /api/tasks`
- `POST /api/tasks/{taskId}/confirm`
- `POST /api/accounts`
- `GET /api/accounts/capabilities`
- `POST /api/catalog/import`
- `POST /api/sales/import`
- `POST /api/reviews/import`
- `POST /api/claims/import`
- `POST /api/pvz/import`
- `POST /api/operational-data/import`
- `GET /api/operational-data/{kind}`
- `POST /api/memory`
- `POST /api/memory/search`
- `POST /api/accounts/{accountId}/validate`
- `POST /api/accounts/{accountId}/sync/catalog`
- `POST /api/accounts/{accountId}/write-scopes`
- `GET /api/readiness`
- `GET /api/brain/architecture-review`
- `GET /api/brain/architecture-gate`
- `GET /api/brain/llm-status`
- `POST /api/self-update/plan`
- `POST /api/self-update/run`
- `POST /api/claim-deadlines`
- `GET /api/claim-deadlines`

Production auth:

- `POST /api/auth/telegram` accepts Telegram Mini App `initData`, validates the Telegram HMAC and returns a short-lived bearer token.
- `Authorization: Bearer <session>` is the production API context. Tenant, user and role are taken from the verified token, not from caller-supplied tenant headers.

Local/test-only headers:

- `X-Tenant-Id`: seller or PVZ owner scope.
- `X-User-Id`: current operator.
- `X-Role`: `owner`, `manager`, `pvz_operator` or `support`.
- `X-Idempotency-Key`: required for safe repeated confirmations.

Readiness statuses:

- `ready_for_safe_pilot`: backend, bot and Mini App are usable for a safe pilot with connected/imported tenant data, but live marketplace writes remain locked.
- `blocked_for_live_pilot`: at least one real account, claim policy, marketplace verification step or LLM architecture gate is missing before live sellers.
- `ready_for_live_pilot`: accounts are validated, source-linked claim windows are present and an architecture gate pass is recorded.

Live write readiness:

- Read access and write access are checked separately. Even if a cabinet token can read products, live writes stay blocked until an owner verifies the exact write scopes (`catalog`, `reviews`, `ads`) with a source URL and evidence.
- `/api/readiness` returns `writeScopeBlockers` such as `ozon:ads`, so Telegram/Mini App can explain in plain language which real action is still locked.

LLM safety:

- The default provider is local/offline so tests and pilots do not spend external tokens by accident.
- External LLM calls use an OpenAI-compatible endpoint from env and are treated as optional acceleration, not a hard dependency.
- The router redacts secrets, enforces token budgets and checks the actual returned model/provider before recording a live pass.
- `/api/brain/architecture-gate` does not spend tokens by default; `?live=true` still stays offline unless `LLM_SMOKE_ENABLED=true` and a provider key is configured.
- `/api/brain/llm-status?live=true` performs a real model-list check only when `LLM_SMOKE_ENABLED=true`; otherwise it reports configuration without spending tokens.
