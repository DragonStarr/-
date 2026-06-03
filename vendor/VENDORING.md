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

The current repository keeps first-party adapters and empty snapshot markers only. Real third-party
copies are added component by component when a license-safe implementation is selected.
