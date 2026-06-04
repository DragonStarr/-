# Plugin Manifest SDK

User extensions are buttons described by JSON/YAML manifests. They compose existing safe actions.
They do not execute arbitrary code.

```json
{
  "id": "daily_margin",
  "label": "Проверить маржу",
  "surface": "both",
  "moduleId": "M08_FINANCE",
  "action": "show_tasks",
  "inputSchema": {
    "type": "object",
    "properties": {
      "period": { "type": "string", "enum": ["today", "week"] }
    }
  },
  "scopes": ["finance:read"],
  "requiredRole": "owner",
  "requiresConfirm": true,
  "activate": false
}
```

## Safety

- `id` uses lowercase latin/digits/dot/dash/underscore.
- `label` must be plain Russian text, not a command.
- `action` must be whitelisted by `operator_day.plugins.registry`.
- Owner reviews and activates the manifest.
- New code requests go to the self-update/Codex pipeline, not to runtime execution.
