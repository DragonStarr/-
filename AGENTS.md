# Project Operating Rules

## Product

- This repository is `mpomoshchnik / Operator Day`: Telegram bot plus Mini App for marketplace sellers and PVZ owners.
- The product is considered ready only when the full TZ, all correction notebooks, visual checks, tests, server flow, data flow, safety gates, and Git handoff are closed.
- Do not call a build "ready" from screenshots, plans, or partial demos. Readiness needs passing checks and clear evidence.

## Safety

- Never commit real API keys, Telegram tokens, marketplace tokens, GitHub tokens, cookies, session strings, or screenshots/logs that expose secrets.
- Use placeholders in examples. Redact secrets in API responses, logs, audit records, and docs.
- No marketplace write is allowed without explicit user confirmation, idempotency, role check, audit event, and connector safety result.
- In dry-run, simulation, missing-key, or local-artifact mode, return `planned`, `escalated`, or `failed`; do not return `done`.
- Do not fake stock, rating, commission, account validation, claim windows, or LLM availability.

## Required Checks

- Backend: `uv run pytest -q`
- Backend style: `uv run ruff check .`
- Mini App types: run `npm run typecheck` inside `apps/miniapp`
- Mini App build: run `npm run build` inside `apps/miniapp`
- Browser QA: verify mobile and desktop Mini App after UI changes.
- Secret scan: search changed files before commit for real-looking keys and tokens.

## Architecture

- Keep tenant boundaries explicit. Every seller/PVZ business record must be tenant-scoped.
- Prefer official marketplace API contracts and owner-imported data over guessed values.
- Keep connector operations behind safety/catalog layers; do not scatter raw marketplace calls through modules.
- The LLM layer helps with reasoning, drafts, and architecture gates, but business actions must stay deterministic and auditable.
- Self-update must use last-known-good snapshots, sandbox checks, tests, and no automatic promotion on unverified changes.

## UX

- User-facing Russian should be simple: buttons and clear outcomes, not technical commands.
- Do not show fake Telegram status bars or phone chrome inside the Mini App.
- Separate "план сохранён / проверено без ключей" from "выполнено".
- Avoid intermediate-product wording in the product UI. Use "безопасный тест" for simulated mode and "живая работа" for real mode.

## Git

- Work in scoped, reviewable diffs.
- Do not touch unrelated repositories or platform folders.
- Do not push unless a correct remote exists and the user has allowed that target.
