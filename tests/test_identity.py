from sqlalchemy import select

from operator_day.domain import Role
from operator_day.models import Tenant, User
from operator_day.repositories import UserRepository


async def test_telegram_identity_creates_isolated_tenant(session_factory) -> None:
    async with session_factory() as session:
        repo = UserRepository(session)

        first = await repo.context_for_telegram("10001", "Мария")
        second = await repo.context_for_telegram("10002", "Иван")
        first_again = await repo.context_for_telegram("10001", "Мария")

        tenants = (await session.execute(select(Tenant))).scalars().all()
        users = (await session.execute(select(User))).scalars().all()

    assert first.tenant_id != second.tenant_id
    assert first.tenant_id == first_again.tenant_id
    assert first.role == Role.OWNER
    assert len(tenants) == 2
    assert len(users) == 2
