# Vendoring

Runtime must not depend on live upstream repositories. Useful external code is copied into
`vendor/` only after license review, hash recording and adapter wrapping.

## Rules

- Keep source URL, commit or tag, license, snapshot date and SHA256 for every component.
- Use `vendor/_snapshots/current` as last known good.
- Never import upstream code directly from GitHub at runtime.
- AGPL/GPL code may be documented as inspiration or isolated as a separate service, not linked into the core.
- All updates go through self-update gates: mirror, prompt-injection scan, sandbox build, contract tests, LLM review, canary, rollback.

## Current Snapshot

The current repository keeps first-party adapters in `operator_day/connectors/`, local
payload builders in `vendor/marketplace_sdk/` and a last-known-good operation manifest in
`vendor/_snapshots/current/marketplace_operations.manifest.json`.

That means runtime does not fetch SDK code from GitHub. External repositories and official docs are
used as update inputs only. A future third-party SDK copy may be added here only after license review,
hash recording, adapter wrapping and green self-update gates.
