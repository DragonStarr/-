from httpx import ASGITransport, AsyncClient

from operator_day.main import create_app

HEADERS = {
    "X-Tenant-Id": "simulated-real-seller",
    "X-User-Id": "owner",
    "X-Role": "owner",
}


async def test_real_seller_and_pvz_rehearsal_without_external_keys() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        account = await client.post(
            "/api/accounts",
            headers=HEADERS,
            json={
                "platform": "ozon",
                "title": "Ozon safe rehearsal",
                "apiKey": "placeholder-token-only",
                "clientId": "client-1",
                "performanceClientId": "perf-client",
                "performanceClientSecret": "placeholder-performance-secret",
                "reviewManagementSubscription": True,
            },
        )
        account_id = account.json()["accountId"]

        validate_plan = await client.post(
            f"/api/accounts/{account_id}/validate",
            headers=HEADERS,
            json={"dryRun": True},
        )
        sync_plan = await client.post(
            f"/api/accounts/{account_id}/sync/catalog",
            headers=HEADERS,
            json={"dryRun": True},
        )
        claim_policy = await client.post(
            "/api/claim-deadlines",
            headers=HEADERS,
            json={
                "platform": "ozon",
                "claimType": "lost_or_damaged",
                "days": 30,
                "sourceUrl": "https://seller.example.test/claim-deadline-policy",
                "note": "Owner verified rehearsal policy",
            },
        )
        catalog = await client.post(
            "/api/catalog/import",
            headers=HEADERS,
            json={
                "accountId": account_id,
                "source": "safe-rehearsal",
                "products": [
                    {
                        "sku": "SIM-SELLER-1",
                        "title": "Rehearsal product",
                        "price": 1700,
                        "cost": 1550,
                        "stock": 3,
                        "commissionRate": 0.25,
                        "rating": 4.7,
                    }
                ],
            },
        )
        sales = await client.post(
            "/api/sales/import",
            headers=HEADERS,
            json={
                "accountId": account_id,
                "sales": [
                    {
                        "platform": "ozon",
                        "saleId": "sale-sim-1",
                        "sku": "SIM-SELLER-1",
                        "soldAt": "2026-06-04T09:00:00Z",
                        "quantity": 8,
                        "revenue": 13600,
                    }
                ],
            },
        )
        reviews = await client.post(
            "/api/reviews/import",
            headers=HEADERS,
            json={
                "reviews": [
                    {
                        "platform": "ozon",
                        "reviewId": "review-positive-sim",
                        "sku": "SIM-SELLER-1",
                        "rating": 5,
                        "text": "Delivery was fast and the product is good.",
                        "source": "safe-rehearsal",
                    },
                    {
                        "platform": "ozon",
                        "reviewId": "review-negative-sim",
                        "sku": "SIM-SELLER-1",
                        "rating": 2,
                        "text": "The item arrived damaged and needs a refund.",
                        "source": "safe-rehearsal",
                    },
                ]
            },
        )
        claims = await client.post(
            "/api/claims/import",
            headers=HEADERS,
            json={
                "claims": [
                    {
                        "platform": "ozon",
                        "claimId": "claim-sim-1",
                        "claimType": "lost_or_damaged",
                        "sku": "SIM-SELLER-1",
                        "amount": 4200,
                        "reason": "Lost item compensation was not paid.",
                        "evidence": ["shipment act", "weekly report", "stock movement"],
                        "discoveredAt": "2026-06-04T10:00:00Z",
                        "source": "safe-rehearsal",
                    }
                ]
            },
        )
        pvz = await client.post(
            "/api/pvz/import",
            headers=HEADERS,
            json={
                "points": [
                    {
                        "pointId": "pvz-sim-1",
                        "title": "PVZ safe rehearsal",
                        "monthlyTurnover": 1800000,
                        "employees": [
                            {"employeeId": "emp-1", "name": "Anna", "hourlyRate": 260},
                            {"employeeId": "emp-2", "name": "Igor", "hourlyRate": 290},
                        ],
                    }
                ]
            },
        )
        for kind, records in {
            "rule_changes": [
                {
                    "id": "rule-sim-1",
                    "title": "Marketplace tariff changed",
                    "source": "official-rules-feed",
                    "source_url": "https://seller.example.test/tariff-change",
                    "affected_revenue": 15000,
                    "impact": "margin",
                }
            ],
            "cash_ops": [
                {
                    "id": "cash-sim-1",
                    "title": "PVZ cash mismatch",
                    "source": "safe-rehearsal",
                    "amount": 110000,
                    "unmatched_amount": 2500,
                }
            ],
            "studio_specs": [
                {
                    "id": "studio-sim-1",
                    "title": "Add weekly reconciliation button",
                    "module_id": "M08_FINANCE",
                    "source": "seller-request",
                }
            ],
            "incidents": [
                {
                    "id": "incident-sim-1",
                    "title": "LLM token budget is near the limit",
                    "severity": "high",
                    "status": "open",
                    "source": "budget-guard",
                }
            ],
            "eval_runs": [
                {
                    "id": "eval-sim-1",
                    "title": "Review answer quality dropped",
                    "score": 0.61,
                    "prompt_version": "reviews-v3",
                    "source": "feedback-loop",
                }
            ],
            "source_changes": [
                {
                    "id": "source-sim-1",
                    "title": "Connector SDK release candidate",
                    "source": "github-radar",
                    "source_url": "https://github.com/example/operator-day-sdk",
                }
            ],
        }.items():
            imported = await client.post(
                "/api/operational-data/import",
                headers=HEADERS,
                json={"kind": kind, "records": records},
            )
            assert imported.status_code == 200

        self_update = await client.post(
            "/api/self-update/plan",
            headers=HEADERS,
            json={"source": "https://github.com/example/operator-day-sdk"},
        )
        tasks_response = await client.get("/api/tasks/morning?limit=100", headers=HEADERS)
        tasks = tasks_response.json()
        modules = {task["moduleId"] for task in tasks}
        positive_review = next(
            task
            for task in tasks
            if task["moduleId"] == "M05_REVIEWS"
            and task["payload"].get("review_id") == "review-positive-sim"
        )
        confirmed = await client.post(
            f"/api/tasks/{positive_review['taskId']}/confirm",
            headers={**HEADERS, "X-Idempotency-Key": "positive-review-sim"},
        )
        repeated = await client.post(
            f"/api/tasks/{positive_review['taskId']}/confirm",
            headers={**HEADERS, "X-Idempotency-Key": "positive-review-sim"},
        )
        denied = await client.post(
            f"/api/tasks/{positive_review['taskId']}/confirm",
            headers={
                "X-Tenant-Id": HEADERS["X-Tenant-Id"],
                "X-User-Id": "pvz-operator",
                "X-Role": "pvz_operator",
                "X-Idempotency-Key": "pvz-denied",
            },
        )
        safe_release = await client.get("/api/release-gate?simulation=true", headers=HEADERS)
        live_release = await client.get("/api/release-gate?simulation=false", headers=HEADERS)

    assert account.status_code == 200
    assert validate_plan.status_code == 200
    assert sync_plan.status_code == 200
    assert claim_policy.status_code == 200
    assert catalog.status_code == 200
    assert sales.status_code == 200
    assert reviews.status_code == 200
    assert claims.status_code == 200
    assert pvz.status_code == 200
    assert self_update.status_code == 200
    assert "placeholder-token-only" not in str(
        [
            account.json(),
            validate_plan.json(),
            sync_plan.json(),
            safe_release.json(),
            live_release.json(),
        ]
    )
    assert validate_plan.json()["dryRun"] is True
    assert sync_plan.json()["dryRun"] is True
    assert self_update.json()["status"] == "planned"
    assert {
        "M02_UNIT",
        "M05_REVIEWS",
        "M08_FINANCE",
        "M11_PVZ",
        "M12_RULES",
        "M14_ACCOUNTING",
        "M15_BILLING",
        "M16_SUPERVISOR",
        "M17_LEARNING",
        "M18_RADAR",
        "M20_CLAIMS",
    }.issubset(modules)
    assert all(len(task["payload"].get("skills", [])) >= 30 for task in tasks)
    assert all(len(task["payload"].get("mcp_checks", [])) == 10 for task in tasks)
    assert confirmed.status_code == 200
    assert repeated.status_code == 200
    assert confirmed.json() == repeated.json()
    assert confirmed.json()["status"] in {"planned", "done"}
    assert confirmed.json()["auditEvent"]["connector_status"] in {"prepared", "recorded"}
    assert denied.status_code == 403
    assert safe_release.json()["summary"]["total"] == 20
    assert safe_release.json()["summary"]["blocked"] == 0
    assert safe_release.json()["overallStatus"] == "ready_under_simulation"
    assert live_release.json()["overallStatus"] == "blocked_for_real_use"
    assert "marketplace_api_verification" in live_release.json()["liveBlockers"]
    assert "prod_llm_gate" in live_release.json()["liveBlockers"]
