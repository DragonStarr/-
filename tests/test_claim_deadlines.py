from httpx import ASGITransport, AsyncClient

from operator_day.main import create_app


async def test_owner_can_store_source_linked_claim_deadline_policy() -> None:
    headers = {"X-Tenant-Id": "claims-tenant", "X-User-Id": "owner", "X-Role": "owner"}
    payload = {
        "platform": "ozon",
        "claimType": "lost_or_damaged",
        "days": 30,
        "sourceUrl": "https://docs.ozon.ru/",
        "note": "Проверено по кабинету",
    }

    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        created = await client.post("/api/claim-deadlines", headers=headers, json=payload)
        listed = await client.get("/api/claim-deadlines", headers=headers)

    assert created.status_code == 200
    assert created.json()["platform"] == "ozon"
    assert created.json()["sourceUrl"] == "https://docs.ozon.ru/"
    assert listed.json()[0]["claimType"] == "lost_or_damaged"


async def test_non_owner_cannot_store_claim_deadline_policy() -> None:
    headers = {"X-Tenant-Id": "claims-tenant", "X-User-Id": "pvz", "X-Role": "pvz_operator"}

    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/claim-deadlines",
            headers=headers,
            json={
                "platform": "wb",
                "claimType": "lost_or_damaged",
                "days": 14,
                "sourceUrl": "https://dev.wildberries.ru/",
            },
        )

    assert response.status_code == 403
