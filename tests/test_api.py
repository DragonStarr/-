from httpx import ASGITransport, AsyncClient

from operator_day.api import routes
from operator_day.api.routes import _confirm_out
from operator_day.connectors.transport import MarketplaceApiError
from operator_day.domain import ActionResult, TaskStatus
from operator_day.main import create_app


async def test_health() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_morning_and_confirm_flow() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        tasks_response = await client.get("/api/tasks/morning")
        task = tasks_response.json()[0]
        confirm_response = await client.post(f"/api/tasks/{task['taskId']}/confirm")
        feedback_response = await client.post(
            "/api/feedback",
            json={"taskId": task["taskId"], "score": 5, "comment": "ok"},
        )

    assert tasks_response.status_code == 200
    assert "score" in task
    assert "moneyEffect" in task
    assert confirm_response.status_code == 200
    assert feedback_response.status_code == 200
    assert confirm_response.json()["taskId"] == task["taskId"]
    assert feedback_response.json()["status"] == "saved"


async def test_confirm_masks_marketplace_failure_without_execution_record(monkeypatch) -> None:
    headers = {
        "X-Tenant-Id": "api-marketplace-failure",
        "X-User-Id": "owner",
        "X-Role": "owner",
    }

    class FailingMorningOrchestrator:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def execute_prepared(self, ctx, task):
            raise MarketplaceApiError("leaked-internal-marketplace-error")

    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        tasks_response = await client.get("/api/tasks/morning?limit=1", headers=headers)
        task_id = tasks_response.json()[0]["taskId"]
        monkeypatch.setattr(routes, "MorningOrchestrator", FailingMorningOrchestrator)
        confirm_response = await client.post(
            f"/api/tasks/{task_id}/confirm",
            headers={**headers, "X-Idempotency-Key": "marketplace-failure"},
        )

    assert tasks_response.status_code == 200
    assert confirm_response.status_code == 502
    assert "leaked-internal-marketplace-error" not in str(confirm_response.json())
    assert "ничего не изменили" in confirm_response.json()["detail"].lower()


async def test_morning_tasks_do_not_expose_internal_modes_to_user() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.get("/api/tasks/morning?limit=50")

    assert response.status_code == 200
    for task in response.json():
        visible_text = " ".join(
            str(task[key]) for key in ("title", "shortText", "actionLabel")
        ).lower()
        assert "replay" not in visible_text
        assert "dry-run" not in visible_text
        assert "dry_run" not in visible_text


def test_confirm_response_sanitizes_stale_done_wording() -> None:
    result = ActionResult(
        task_id="stale-result",
        status=TaskStatus.DONE,
        user_text="Готово. Действие записано в журнал.",
        audit_event={"connector_status": "recorded"},
    )

    assert _confirm_out(result).text == "Записал. Действие записано в журнал."


async def test_account_catalog_sync_dry_run_is_owner_only_and_redacts_secret() -> None:
    headers = {"X-Tenant-Id": "api-sync-tenant", "X-User-Id": "owner", "X-Role": "owner"}
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        account_response = await client.post(
            "/api/accounts",
            headers=headers,
            json={
                "platform": "ozon",
                "title": "Ozon test",
                "apiKey": "seller-secret-token",
                "clientId": "client-1",
            },
        )
        account_id = account_response.json()["accountId"]
        denied_response = await client.post(
            f"/api/accounts/{account_id}/sync/catalog",
            headers={**headers, "X-Role": "manager"},
            json={"dryRun": True},
        )
        sync_response = await client.post(
            f"/api/accounts/{account_id}/sync/catalog",
            headers=headers,
            json={"dryRun": True},
        )

    assert account_response.status_code == 200
    assert denied_response.status_code == 403
    assert sync_response.status_code == 200
    payload = sync_response.json()
    assert payload["dryRun"] is True
    assert payload["source"] == "ozon"
    assert payload["plannedOperation"]["operationId"] == "ProductAPI_GetProductList"
    assert "seller-secret-token" not in str(payload)


async def test_account_validation_dry_run_is_owner_only() -> None:
    headers = {
        "X-Tenant-Id": "api-validate-tenant",
        "X-User-Id": "owner",
        "X-Role": "owner",
    }
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        account_response = await client.post(
            "/api/accounts",
            headers=headers,
            json={
                "platform": "wb",
                "title": "WB test",
                "apiKey": "wb-secret-token",
            },
        )
        account_id = account_response.json()["accountId"]
        denied_response = await client.post(
            f"/api/accounts/{account_id}/validate",
            headers={**headers, "X-Role": "manager"},
            json={"dryRun": True},
        )
        validate_response = await client.post(
            f"/api/accounts/{account_id}/validate",
            headers=headers,
            json={"dryRun": True},
        )

    assert denied_response.status_code == 403
    assert validate_response.status_code == 200
    body = validate_response.json()
    assert body["dryRun"] is True
    assert body["plannedOperation"]["operationId"] == "WB_Content_GetCardsList"
    assert "wb-secret-token" not in str(body)


async def test_write_scope_verification_requires_owner_and_validated_account() -> None:
    headers = {
        "X-Tenant-Id": "api-write-scope-tenant",
        "X-User-Id": "owner",
        "X-Role": "owner",
    }
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        account_response = await client.post(
            "/api/accounts",
            headers=headers,
            json={
                "platform": "ozon",
                "title": "Ozon write scope",
                "apiKey": "ozon-secret-token",
                "clientId": "client-1",
            },
        )
        account_id = account_response.json()["accountId"]
        manager_denied = await client.post(
            f"/api/accounts/{account_id}/write-scopes",
            headers={**headers, "X-Role": "manager"},
            json={
                "scopes": ["catalog"],
                "sourceUrl": "https://seller.example.test/write-probe",
                "evidence": "safe write probe has passed",
            },
        )
        owner_blocked_until_read_validation = await client.post(
            f"/api/accounts/{account_id}/write-scopes",
            headers=headers,
            json={
                "scopes": ["catalog"],
                "sourceUrl": "https://seller.example.test/write-probe",
                "evidence": "safe write probe has passed",
            },
        )

    assert manager_denied.status_code == 403
    assert owner_blocked_until_read_validation.status_code == 409


async def test_yandex_market_account_uses_campaign_id_for_validation_plan() -> None:
    headers = {
        "X-Tenant-Id": "api-ym-tenant",
        "X-User-Id": "owner",
        "X-Role": "owner",
    }
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        account_response = await client.post(
            "/api/accounts",
            headers=headers,
            json={
                "platform": "ym",
                "title": "Yandex test",
                "apiKey": "ym-secret-token",
                "campaignId": "321",
            },
        )
        account_id = account_response.json()["accountId"]
        validate_response = await client.post(
            f"/api/accounts/{account_id}/validate",
            headers=headers,
            json={"dryRun": True},
        )

    assert validate_response.status_code == 200
    body = validate_response.json()
    assert body["plannedOperation"]["operationId"] == "YM_GetOfferPrices"
    assert body["plannedOperation"]["url"].endswith("/v2/campaigns/321/offer-prices")
    assert "ym-secret-token" not in str(body)


async def test_catalog_manual_import_feeds_morning_tasks() -> None:
    headers = {
        "X-Tenant-Id": "api-import-tenant",
        "X-User-Id": "owner",
        "X-Role": "owner",
    }
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        account_response = await client.post(
            "/api/accounts",
            headers=headers,
            json={
                "platform": "ozon",
                "title": "Ozon import",
                "apiKey": "import-secret-token",
                "clientId": "client-1",
                "reviewManagementSubscription": True,
            },
        )
        import_response = await client.post(
            "/api/catalog/import",
            headers=headers,
            json={
                "accountId": account_response.json()["accountId"],
                "source": "manual",
                "products": [
                    {
                        "sku": "IMPORT-1",
                        "title": "Импортный товар",
                        "price": 1000,
                        "cost": 900,
                        "stock": 3,
                        "commissionRate": 0.17,
                        "rating": 4.8,
                    }
                ],
            },
        )
        sales_response = await client.post(
            "/api/sales/import",
            headers=headers,
            json={
                "accountId": account_response.json()["accountId"],
                "sales": [
                    {
                        "platform": "ozon",
                        "saleId": "sale-import-1",
                        "sku": "IMPORT-1",
                        "soldAt": "2026-06-01T08:00:00Z",
                        "quantity": 6,
                        "revenue": 6000,
                    }
                ],
            },
        )
        tasks_response = await client.get(
            "/api/tasks/morning?limit=30",
            headers=headers,
        )

    assert import_response.status_code == 200
    assert import_response.json()["count"] == 1
    assert sales_response.status_code == 200
    assert sales_response.json()["count"] == 1
    assert "import-secret-token" not in str(import_response.json())
    assert "Импортный товар" in str(tasks_response.json())


async def test_reviews_import_feeds_morning_and_confirm_flow() -> None:
    headers = {
        "X-Tenant-Id": "api-reviews-import-tenant",
        "X-User-Id": "owner",
        "X-Role": "owner",
    }
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        imported = await client.post(
            "/api/reviews/import",
            headers=headers,
            json={
                "reviews": [
                    {
                        "platform": "wb",
                        "reviewId": "wb-real-1",
                        "sku": "WB-IMPORT-1",
                        "rating": 5,
                        "text": "Все пришло быстро, товар понравился.",
                        "source": "manual-feedback",
                    },
                    {
                        "platform": "ozon",
                        "reviewId": "oz-real-2",
                        "sku": "OZ-IMPORT-2",
                        "rating": 2,
                        "text": "Товар сломан, хочу возврат.",
                        "source": "manual-feedback",
                    },
                ]
            },
        )
        tasks_response = await client.get("/api/tasks/morning?limit=30", headers=headers)
        reviews = [
            task for task in tasks_response.json() if task["moduleId"] == "M05_REVIEWS"
        ]
        positive = next(task for task in reviews if task["payload"]["review_id"] == "wb-real-1")
        negative = next(task for task in reviews if task["payload"]["review_id"] == "oz-real-2")
        confirmed = await client.post(
            f"/api/tasks/{positive['taskId']}/confirm",
            headers={**headers, "X-Idempotency-Key": "review-positive-1"},
        )

    assert imported.status_code == 200
    assert imported.json()["count"] == 2
    assert positive["risk"] == "confirm"
    assert negative["risk"] == "human"
    assert positive["payload"]["skills"]
    assert len(positive["payload"]["mcp_checks"]) == 10
    assert confirmed.status_code == 200
    assert confirmed.json()["auditEvent"]["connector_status"] == "prepared"
