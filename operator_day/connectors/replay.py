from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from operator_day.connectors.base import ConnectorHealth, MarketplaceClient
from operator_day.db import bind_tenant_scope
from operator_day.domain import (
    ClaimCandidate,
    ClaimDeadlineRule,
    Platform,
    ProductSnapshot,
    PvzEmployee,
    PvzPoint,
    ReviewSnapshot,
    TenantContext,
)
from operator_day.models import (
    Claim,
    ClaimDeadlinePolicy,
    Product,
    PvzEmployeeRecord,
    PvzPointRecord,
    Review,
)


class ReplayMarketplaceClient(MarketplaceClient):
    def __init__(self, platform: Platform) -> None:
        self.platform = platform

    async def validate_capabilities(self) -> ConnectorHealth:
        return ConnectorHealth(
            platform=self.platform,
            mode="replay",
            capabilities={
                "catalog": "ready",
                "reviews": "ready",
                "finance": "replay",
                "ads": "replay",
                "claims": "replay",
            },
            limitations=("live API writes are disabled in replay mode",),
        )

    async def list_products(self) -> list[ProductSnapshot]:
        if self.platform == Platform.WB:
            return [
                ProductSnapshot(
                    Platform.WB, "WB-1001", "Органайзер для кухни", 1290, 7, 720, 0.23, 4.7
                ),
                ProductSnapshot(
                    Platform.WB, "WB-1002", "Термокружка 500 мл", 890, 2, 610, 0.28, 4.2
                ),
            ]
        if self.platform == Platform.OZON:
            return [
                ProductSnapshot(
                    Platform.OZON, "OZ-501", "Кабель USB-C 2 м", 390, 140, 180, 0.31, 4.8
                ),
                ProductSnapshot(
                    Platform.OZON, "OZ-502", "Набор контейнеров", 1590, 11, 1040, 0.34, 4.1
                ),
            ]
        return [
            ProductSnapshot(Platform.YANDEX, "YM-22", "Щетка для обуви", 490, 4, 260, 0.22, 4.5),
        ]

    async def list_reviews(self) -> list[ReviewSnapshot]:
        if self.platform == Platform.WB:
            return [
                ReviewSnapshot(
                    Platform.WB,
                    "wb-review-1",
                    "WB-1001",
                    5,
                    "Все пришло быстро, органайзер удобный.",
                ),
                ReviewSnapshot(
                    Platform.WB,
                    "wb-review-2",
                    "WB-1002",
                    2,
                    "Крышка протекает, хочу вернуть.",
                ),
            ]
        if self.platform == Platform.OZON:
            return [
                ReviewSnapshot(
                    Platform.OZON,
                    "oz-question-1",
                    "OZ-501",
                    5,
                    "Покупатель спрашивает про гарантию.",
                    buyer_question="Подойдет для быстрой зарядки?",
                )
            ]
        return []

    async def send_review_answer(self, review_id: str, answer: str) -> dict[str, str]:
        return {"mode": "replay", "review_id": review_id, "status": "accepted", "answer": answer}


class ReplayHub:
    def __init__(self) -> None:
        self.clients = [
            ReplayMarketplaceClient(Platform.WB),
            ReplayMarketplaceClient(Platform.OZON),
            ReplayMarketplaceClient(Platform.YANDEX),
        ]

    async def products(self) -> list[ProductSnapshot]:
        rows: list[ProductSnapshot] = []
        for client in self.clients:
            rows.extend(await client.list_products())
        return rows

    async def reviews(self) -> list[ReviewSnapshot]:
        rows: list[ReviewSnapshot] = []
        for client in self.clients:
            rows.extend(await client.list_reviews())
        return rows

    async def claim_candidates(self) -> list[ClaimCandidate]:
        return [
            ClaimCandidate(
                platform=Platform.OZON,
                claim_id="replay-lost-1",
                claim_type="lost_or_damaged",
                sku="OZ-501",
                amount=12400,
                reason="Расхождение по складу: товар отгружен, но не отражен в компенсации.",
                evidence=("отгрузка", "остатки", "финотчет"),
                discovered_at=datetime.now(UTC) - timedelta(days=1),
                source="replay",
            )
        ]

    async def claim_deadline_policies(self) -> list[ClaimDeadlineRule]:
        return []

    async def pvz_points(self) -> list[PvzPoint]:
        return [
            PvzPoint(
                point_id="replay-pvz-1",
                title="ПВЗ Replay",
                monthly_turnover=1_800_000,
                employees=(
                    PvzEmployee("replay-anna", "Анна", 220),
                    PvzEmployee("replay-igor", "Игорь", 220),
                ),
            )
        ]

    async def capabilities(self) -> list[ConnectorHealth]:
        return [await client.validate_capabilities() for client in self.clients]

    async def send_review_answer(self, review_id: str, answer: str) -> dict[str, str]:
        for client in self.clients:
            reviews = await client.list_reviews()
            if any(review.review_id == review_id for review in reviews):
                return await client.send_review_answer(review_id, answer)
        return {"mode": "replay", "review_id": review_id, "status": "not_found"}


class DatabaseReplayHub(ReplayHub):
    def __init__(self, session: AsyncSession, ctx: TenantContext) -> None:
        super().__init__()
        self.session = session
        self.ctx = ctx

    async def products(self) -> list[ProductSnapshot]:
        await bind_tenant_scope(self.session, self.ctx)
        rows = (
            await self.session.execute(
                select(Product).where(Product.tenant_id == self.ctx.tenant_id).order_by(Product.sku)
            )
        ).scalars().all()
        if not rows:
            return await super().products()
        return [
            ProductSnapshot(
                platform=_platform_from_category(row.category),
                sku=row.sku,
                name=row.title,
                price=row.price,
                stock=0,
                cost=row.cost,
                commission_rate=0.25,
                rating=0,
            )
            for row in rows
        ]

    async def reviews(self) -> list[ReviewSnapshot]:
        await bind_tenant_scope(self.session, self.ctx)
        rows = (
            await self.session.execute(
                select(Review).where(Review.tenant_id == self.ctx.tenant_id).order_by(Review.id)
            )
        ).scalars().all()
        if not rows:
            return await super().reviews()
        return [
            ReviewSnapshot(
                platform=_platform_from_category(row.source),
                review_id=str((row.payload or {}).get("external_review_id") or row.id),
                sku=row.product_id,
                rating=row.rating,
                text=row.text,
                buyer_question=str((row.payload or {}).get("buyer_question") or "") or None,
            )
            for row in rows
        ]

    async def claim_candidates(self) -> list[ClaimCandidate]:
        await bind_tenant_scope(self.session, self.ctx)
        rows = (
            await self.session.execute(
                select(Claim).where(Claim.tenant_id == self.ctx.tenant_id).order_by(Claim.id)
            )
        ).scalars().all()
        if not rows:
            return await super().claim_candidates()
        return [_claim_candidate_from_row(row) for row in rows]

    async def claim_deadline_policies(self) -> list[ClaimDeadlineRule]:
        await bind_tenant_scope(self.session, self.ctx)
        rows = (
            await self.session.execute(
                select(ClaimDeadlinePolicy).where(
                    ClaimDeadlinePolicy.tenant_id == self.ctx.tenant_id
                )
            )
        ).scalars().all()
        return [
            ClaimDeadlineRule(
                platform=_platform_from_category(row.platform),
                claim_type=row.claim_type,
                days=row.days,
                source_url=row.source_url,
                note=row.note,
            )
            for row in rows
        ]

    async def pvz_points(self) -> list[PvzPoint]:
        await bind_tenant_scope(self.session, self.ctx)
        point_rows = (
            await self.session.execute(
                select(PvzPointRecord)
                .where(PvzPointRecord.tenant_id == self.ctx.tenant_id)
                .order_by(PvzPointRecord.title)
            )
        ).scalars().all()
        if not point_rows:
            return await super().pvz_points()
        employee_rows = (
            await self.session.execute(
                select(PvzEmployeeRecord).where(
                    PvzEmployeeRecord.tenant_id == self.ctx.tenant_id
                )
            )
        ).scalars().all()
        employees_by_point: dict[str, list[PvzEmployee]] = {}
        for row in employee_rows:
            payload = row.payload or {}
            employees_by_point.setdefault(row.point_id, []).append(
                PvzEmployee(
                    employee_id=str(payload.get("external_employee_id") or row.id),
                    name=row.name,
                    hourly_rate=row.hourly_rate,
                    preferred_days=tuple(int(day) for day in (row.preferred_days or [])),
                )
            )
        return [
            PvzPoint(
                point_id=str((row.payload or {}).get("external_point_id") or row.id),
                title=row.title,
                monthly_turnover=row.monthly_turnover,
                employees=tuple(employees_by_point.get(row.id, [])),
            )
            for row in point_rows
        ]

    async def send_review_answer(self, review_id: str, answer: str) -> dict[str, str]:
        await bind_tenant_scope(self.session, self.ctx)
        rows = (
            await self.session.execute(
                select(Review).where(Review.tenant_id == self.ctx.tenant_id)
            )
        ).scalars().all()
        for row in rows:
            payload = row.payload or {}
            if row.id == review_id or payload.get("external_review_id") == review_id:
                row.answer_status = "prepared"
                row.payload = {**payload, "last_answer": answer}
                await self.session.commit()
                break
        return {
            "mode": "database",
            "review_id": review_id,
            "status": "prepared",
            "answer": answer,
        }


def _platform_from_category(value: str) -> Platform:
    try:
        return Platform(value)
    except ValueError:
        return Platform.OZON


def _claim_candidate_from_row(row: Claim) -> ClaimCandidate:
    payload = row.payload or {}
    evidence = payload.get("evidence") or ()
    if isinstance(evidence, str):
        evidence = (evidence,)
    return ClaimCandidate(
        platform=_platform_from_category(row.source),
        claim_id=row.id,
        claim_type=str(payload.get("claim_type") or "lost_or_damaged"),
        sku=row.product_id,
        amount=float(payload.get("amount") or 0),
        reason=str(payload.get("reason") or "Найдена сумма к проверке по претензии."),
        evidence=tuple(str(item) for item in evidence),
        discovered_at=_parse_datetime(payload.get("discovered_at")),
        source=str(payload.get("source") or row.source),
    )


def _parse_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC)
    return datetime.now(UTC)
