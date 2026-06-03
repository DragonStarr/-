from httpx import ASGITransport, AsyncClient

from operator_day.main import create_app


async def test_manager_can_import_pvz_and_feed_morning_schedule() -> None:
    headers = {"X-Tenant-Id": "pvz-import-tenant", "X-User-Id": "manager", "X-Role": "manager"}
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        imported = await client.post(
            "/api/pvz/import",
            headers=headers,
            json={
                "points": [
                    {
                        "pointId": "pvz-1",
                        "title": "PVZ North",
                        "monthlyTurnover": 2_400_000,
                        "employees": [
                            {"employeeId": "emp-1", "name": "Anna", "hourlyRate": 250},
                            {"employeeId": "emp-2", "name": "Igor", "hourlyRate": 300},
                        ],
                    }
                ]
            },
        )
        tasks_response = await client.get("/api/tasks/morning?limit=30", headers=headers)

    assert imported.status_code == 200
    assert imported.json()["count"] == 1
    pvz_task = next(task for task in tasks_response.json() if task["moduleId"] == "M11_PVZ")
    assert pvz_task["payload"]["point_id"] == "pvz-1"
    assert pvz_task["payload"]["point_title"] == "PVZ North"
    assert pvz_task["payload"]["payroll"] == {"Anna": 24000.0, "Igor": 21600.0}
    assert pvz_task["payload"]["skills"]
    assert len(pvz_task["payload"]["mcp_checks"]) == 10


async def test_pvz_operator_cannot_import_staff_rates() -> None:
    headers = {
        "X-Tenant-Id": "pvz-denied-tenant",
        "X-User-Id": "operator",
        "X-Role": "pvz_operator",
    }
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/pvz/import",
            headers=headers,
            json={
                "points": [
                    {
                        "title": "PVZ",
                        "employees": [
                            {"name": "Anna", "hourlyRate": 250},
                            {"name": "Igor", "hourlyRate": 300},
                        ],
                    }
                ]
            },
        )

    assert response.status_code == 403


async def test_pvz_external_ids_are_scoped_per_tenant() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        for tenant in ("pvz-scope-a", "pvz-scope-b"):
            headers = {"X-Tenant-Id": tenant, "X-User-Id": "manager", "X-Role": "manager"}
            imported = await client.post(
                "/api/pvz/import",
                headers=headers,
                json={
                    "points": [
                        {
                            "pointId": "shared-pvz-id",
                            "title": f"PVZ {tenant}",
                            "monthlyTurnover": 900_000,
                            "employees": [
                                {"employeeId": "shared-emp-1", "name": "Anna", "hourlyRate": 250},
                                {"employeeId": "shared-emp-2", "name": "Igor", "hourlyRate": 300},
                            ],
                        }
                    ]
                },
            )
            tasks = await client.get("/api/tasks/morning?limit=30", headers=headers)

            assert imported.status_code == 200
            pvz_task = next(task for task in tasks.json() if task["moduleId"] == "M11_PVZ")
            assert pvz_task["payload"]["point_id"] == "shared-pvz-id"
            assert pvz_task["payload"]["point_title"] == f"PVZ {tenant}"
