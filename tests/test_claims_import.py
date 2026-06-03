from httpx import ASGITransport, AsyncClient

from operator_day.main import create_app


async def test_claim_import_feeds_morning_task_with_source_linked_deadline() -> None:
    headers = {"X-Tenant-Id": "claims-import-tenant", "X-User-Id": "owner", "X-Role": "owner"}
    source_url = "https://seller-edu.ozon.ru/fbs/orders-cancellations-returns/shortfall"
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        policy = await client.post(
            "/api/claim-deadlines",
            headers=headers,
            json={
                "platform": "ozon",
                "claimType": "lost_or_damaged",
                "days": 30,
                "sourceUrl": source_url,
                "note": "Ozon Seller Edu: FBS shortfall check window",
            },
        )
        imported = await client.post(
            "/api/claims/import",
            headers=headers,
            json={
                "claims": [
                    {
                        "platform": "ozon",
                        "claimId": "claim-ozon-1",
                        "claimType": "lost_or_damaged",
                        "sku": "OZ-501",
                        "amount": 3210,
                        "reason": "Товар отгружен, но компенсация не начислена.",
                        "evidence": ["акт отгрузки", "остатки", "финансовый отчет"],
                        "discoveredAt": "2026-06-01T09:00:00+00:00",
                        "source": "manual_reconciliation",
                    }
                ]
            },
        )
        tasks_response = await client.get("/api/tasks/morning?limit=30", headers=headers)

    assert policy.status_code == 200
    assert imported.status_code == 200
    assert imported.json()["count"] == 1
    claims_task = next(
        task for task in tasks_response.json() if task["moduleId"] == "M20_CLAIMS"
    )
    assert claims_task["moneyEffect"] == 3210
    assert claims_task["payload"]["claim_id"] == "claim-ozon-1"
    assert claims_task["payload"]["claim_deadline_needs_verification"] is False
    assert claims_task["payload"]["claim_deadline_days"] == 30
    assert claims_task["payload"]["claim_deadline_source_url"] == source_url
    assert claims_task["payload"]["mcp_checks"]


async def test_claim_import_without_policy_keeps_deadline_verification_flag() -> None:
    headers = {
        "X-Tenant-Id": "claims-no-policy-tenant",
        "X-User-Id": "owner",
        "X-Role": "owner",
    }
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        imported = await client.post(
            "/api/claims/import",
            headers=headers,
            json={
                "claims": [
                    {
                        "platform": "wb",
                        "claimType": "overcharge",
                        "sku": "WB-404",
                        "amount": 990,
                        "reason": "Лишнее удержание в недельном отчете.",
                        "evidence": ["недельный отчет", "заказ", "тариф"],
                        "discoveredAt": "2026-06-02T09:00:00+00:00",
                    }
                ]
            },
        )
        tasks_response = await client.get("/api/tasks/morning?limit=30", headers=headers)

    assert imported.status_code == 200
    claims_task = next(
        task for task in tasks_response.json() if task["moduleId"] == "M20_CLAIMS"
    )
    assert claims_task["payload"]["platform"] == "wb"
    assert claims_task["payload"]["claim_deadline_needs_verification"] is True
