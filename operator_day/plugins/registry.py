from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from operator_day.modules.implementations import ModuleRegistry

PLUGIN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,80}$")
ALLOWED_ACTIONS = {
    "show_tasks",
    "confirm_task",
    "import_catalog",
    "import_reviews",
    "import_claims",
    "import_pvz",
    "sync_catalog",
    "validate_account",
    "open_miniapp",
}


class PluginManifestSpec(BaseModel):
    id: str = Field(min_length=3, max_length=80)
    label: str = Field(min_length=2, max_length=80)
    surface: Literal["bot", "miniapp", "both"] = "both"
    module_id: str = Field(alias="moduleId", min_length=2, max_length=20)
    action: str = Field(min_length=3, max_length=80)
    input_schema: dict[str, Any] = Field(default_factory=dict, alias="inputSchema")
    scopes: list[str] = Field(default_factory=list, max_length=20)
    required_role: Literal["owner", "manager", "pvz_operator", "support"] = Field(
        default="owner",
        alias="requiredRole",
    )
    requires_confirm: bool = Field(default=True, alias="requiresConfirm")

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not PLUGIN_ID_RE.match(value):
            raise ValueError("id must be lowercase latin, digits, dot, dash or underscore")
        return value

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        if "/" in value or "\\" in value:
            raise ValueError("label must be plain user-facing text, not a command")
        return value.strip()

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in ALLOWED_ACTIONS:
            raise ValueError("action is not allowed")
        return value


def validate_plugin_manifest(payload: dict[str, Any]) -> PluginManifestSpec:
    manifest = PluginManifestSpec.model_validate(payload)
    module_ids = {module.module_id.value for module in ModuleRegistry.default().modules}
    if manifest.module_id not in module_ids:
        raise ValueError("moduleId is not registered")
    return manifest
