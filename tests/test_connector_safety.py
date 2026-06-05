import pytest

from operator_day.connectors.base import MarketplaceClient
from operator_day.connectors.replay import ReplayHub
from operator_day.connectors.safety import (
    MarketplaceOperation,
    OperationSafety,
    ensure_operation_allowed,
)


def test_read_operation_is_allowed_without_confirmation() -> None:
    operation = MarketplaceOperation(
        operation_id="ProductAPI_GetProductList",
        platform="ozon",
        safety=OperationSafety.READ,
    )

    ensure_operation_allowed(operation)


def test_write_operation_requires_confirm_write() -> None:
    operation = MarketplaceOperation(
        operation_id="ReviewAPI_SendAnswer",
        platform="ozon",
        safety=OperationSafety.WRITE,
    )

    with pytest.raises(PermissionError, match="confirm_write"):
        ensure_operation_allowed(operation)

    ensure_operation_allowed(operation, confirm_write=True)


def test_destructive_operation_requires_double_confirmation() -> None:
    operation = MarketplaceOperation(
        operation_id="Campaign_Delete",
        platform="ozon",
        safety=OperationSafety.DESTRUCTIVE,
    )

    with pytest.raises(PermissionError, match="destructive"):
        ensure_operation_allowed(operation, confirm_write=True)

    ensure_operation_allowed(
        operation,
        confirm_write=True,
        confirm_destructive=True,
    )


async def test_replay_hub_reports_capabilities() -> None:
    capabilities = await ReplayHub().capabilities()

    assert len(capabilities) == 3
    assert capabilities[0].mode == "replay"
    assert capabilities[0].capabilities["catalog"] == "ready"


def test_marketplace_client_requires_explicit_capability_validation() -> None:
    assert "validate_capabilities" in MarketplaceClient.__abstractmethods__
