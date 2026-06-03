from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from operator_day.brain.orchestrator import MorningOrchestrator
from operator_day.domain import Role, TenantContext
from operator_day.models import AuditLog, Base, Feedback
from operator_day.repositories import TaskRepository


async def test_task_repository_persists_confirm_and_feedback() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    ctx = TenantContext(tenant_id="t-db", user_id="u-db", role=Role.OWNER)
    orchestrator = MorningOrchestrator()

    async with session_factory() as session:
        repo = TaskRepository(session)
        tasks = await orchestrator.morning_top(ctx, limit=3)

        await repo.save_tasks(ctx, tasks)
        restored = await repo.get_task(ctx, tasks[0].task_id)

        assert restored is not None
        assert restored.title == tasks[0].title
        assert len(await repo.list_tasks(ctx)) == 3

        result = await orchestrator.execute_prepared(ctx, restored)
        await repo.save_result(ctx, restored, result)
        await repo.save_feedback(ctx, restored.task_id, score=5, comment="ok")

        audit_rows = (await session.execute(select(AuditLog))).scalars().all()
        feedback_rows = (await session.execute(select(Feedback))).scalars().all()

        assert audit_rows[0].before_after["tenant_id"] == "t-db"
        assert feedback_rows[0].task_id == restored.task_id

    await engine.dispose()
