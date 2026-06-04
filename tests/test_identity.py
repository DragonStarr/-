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


async def test_existing_telegram_identity_keeps_stored_tenant_and_role(
    session_factory,
) -> None:
    async with session_factory() as session:
        session.add(Tenant(id="seller-existing", title="Existing seller"))
        session.add(
            User(
                id="manager-existing",
                tenant_id="seller-existing",
                tg_id="20001",
                role=Role.MANAGER.value,
                name="Manager",
            )
        )
        await session.commit()

        ctx = await UserRepository(session).context_for_telegram("20001", "Ignored")

    assert ctx.tenant_id == "seller-existing"
    assert ctx.user_id == "manager-existing"
    assert ctx.role == Role.MANAGER
