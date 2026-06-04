from __future__ import annotations

import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from operator_day.bot.keyboards import (
    accounts_keyboard,
    main_menu,
    miniapp_keyboard,
    task_keyboard,
)
from operator_day.bot.render import render_accounts_status, render_task, render_welcome
from operator_day.brain.orchestrator import MorningOrchestrator
from operator_day.connectors.live_sync import (
    plan_catalog_sync_for_account,
    sync_ozon_catalog_for_account,
    validate_account_for_read_access,
)
from operator_day.connectors.replay import DatabaseReplayHub
from operator_day.connectors.transport import MarketplaceApiError
from operator_day.db import ensure_local_database, get_sessionmaker
from operator_day.domain import TenantContext
from operator_day.repositories import (
    AccountRepository,
    ClaimPolicyRepository,
    ReadinessRepository,
    TaskRepository,
    UserRepository,
)

router = Router()


async def user_context(message: Message | CallbackQuery) -> TenantContext:
    user = message.from_user
    user_id = str(user.id if user else "demo")
    name = user.full_name if user else ""
    await ensure_local_database()
    async with get_sessionmaker()() as session:
        return await UserRepository(session).context_for_telegram(user_id, name)


@router.message(F.text.in_({"/start", "Старт"}))
async def start(message: Message) -> None:
    await message.answer(render_welcome(), reply_markup=main_menu())
    await message.answer("Для большого экрана откройте Mini App.", reply_markup=miniapp_keyboard())


@router.message(F.text == "Дела")
async def morning(message: Message) -> None:
    ctx = await user_context(message)
    async with get_sessionmaker()() as session:
        tasks = await MorningOrchestrator(replay=DatabaseReplayHub(session, ctx)).morning_top(ctx)
        await TaskRepository(session).save_tasks(ctx, tasks)
    await message.answer(f"Нашёл {len(tasks)} главных дел.", reply_markup=main_menu())
    for task in tasks:
        await message.answer(render_task(task), reply_markup=task_keyboard(task))


@router.message(F.text == "Кабинеты")
async def accounts(message: Message) -> None:
    ctx = await user_context(message)
    async with get_sessionmaker()() as session:
        account_repo = AccountRepository(session)
        rows = await account_repo.list_accounts(ctx)
        write_scope_blockers = await account_repo.missing_write_scope_verifications(ctx)
        claim_policies = await ClaimPolicyRepository(session).list_deadline_policies(ctx)
        gate_passed = await ReadinessRepository(session).has_passed_architecture_gate(ctx)
    live_blockers: list[str] = []
    if any(account.status != "validated" for account in rows):
        live_blockers.append("marketplace_api_verification")
    if rows and write_scope_blockers:
        live_blockers.append("marketplace_write_scope_verification")
    if rows and not claim_policies:
        live_blockers.append("claim_deadline_policies")
    if rows and not gate_passed:
        live_blockers.append("prod_llm_gate")
    await message.answer(
        render_accounts_status(
            rows,
            live_blockers=live_blockers,
            write_scope_blockers=write_scope_blockers,
        ),
        reply_markup=accounts_keyboard(rows) or main_menu(),
    )


@router.message(F.text == "Финансы")
async def finance(message: Message) -> None:
    ctx = await user_context(message)
    async with get_sessionmaker()() as session:
        tasks = [
            task
            for task in await MorningOrchestrator(
                replay=DatabaseReplayHub(session, ctx)
            ).collect_all(ctx)
            if task.module_id.value in {"M08_FINANCE", "M20_CLAIMS"}
        ]
    if not tasks:
        await message.answer("Финансовых дел пока нет.", reply_markup=main_menu())
    for task in tasks:
        await message.answer(render_task(task), reply_markup=task_keyboard(task))


@router.message(F.text == "ПВЗ")
async def pvz(message: Message) -> None:
    ctx = await user_context(message)
    async with get_sessionmaker()() as session:
        tasks = [
            task
            for task in await MorningOrchestrator(
                replay=DatabaseReplayHub(session, ctx)
            ).collect_all(ctx)
            if task.module_id.value == "M11_PVZ"
        ]
    if not tasks:
        await message.answer("Дел по ПВЗ пока нет.", reply_markup=main_menu())
    for task in tasks:
        await message.answer(render_task(task), reply_markup=task_keyboard(task))


@router.message(F.text == "Настройки")
async def settings(message: Message) -> None:
    await message.answer(
        "Пилотный режим включён. Реальные ключи кабинетов хранятся только в env/хранилище.",
        reply_markup=main_menu(),
    )
    await message.answer("Экран ассистента:", reply_markup=miniapp_keyboard())


@router.callback_query(F.data.startswith("task:confirm:"))
async def confirm_task(callback: CallbackQuery) -> None:
    task_id = callback.data.split(":")[-1] if callback.data else ""
    ctx = await user_context(callback)
    async with get_sessionmaker()() as session:
        repo = TaskRepository(session)
        existing = await repo.get_execution(ctx, task_id, task_id)
        if existing is not None:
            await callback.answer("Уже записано")
            await callback.message.answer(existing.user_text)  # type: ignore[union-attr]
            return
        task = await repo.get_task(ctx, task_id)
        if task is None:
            await callback.answer("Дело уже не найдено", show_alert=True)
            return
        try:
            result = await MorningOrchestrator(
                replay=DatabaseReplayHub(session, ctx)
            ).execute_prepared(ctx, task)
        except (MarketplaceApiError, httpx.HTTPError):
            await callback.answer("Кабинет не принял действие", show_alert=True)
            await callback.message.answer(  # type: ignore[union-attr]
                "Кабинет маркетплейса не принял действие. Мы ничего не изменили; "
                "проверьте доступы и повторите."
            )
            return
        await TaskRepository(session).save_result(ctx, task, result, idempotency_key=task_id)
    await callback.answer("Записал")
    await callback.message.answer(result.user_text)  # type: ignore[union-attr]


@router.callback_query(F.data.startswith("task:show:"))
async def show_task(callback: CallbackQuery) -> None:
    task_id = callback.data.split(":")[-1] if callback.data else ""
    ctx = await user_context(callback)
    async with get_sessionmaker()() as session:
        task = await TaskRepository(session).get_task(ctx, task_id)
    if task is None:
        await callback.answer("Дело уже не найдено", show_alert=True)
        return
    await callback.answer("Показываю")
    await callback.message.answer(render_task(task))  # type: ignore[union-attr]


@router.callback_query(F.data.startswith("account:validate:"))
async def validate_account(callback: CallbackQuery) -> None:
    account_id = callback.data.split(":")[-1] if callback.data else ""
    ctx = await user_context(callback)
    try:
        async with get_sessionmaker()() as session:
            await validate_account_for_read_access(session, ctx, account_id)
    except Exception:
        await callback.answer("Кабинет пока не отвечает", show_alert=True)
        await callback.message.answer(  # type: ignore[union-attr]
            "Не получилось проверить кабинет. "
            "Проверьте ключ в личном кабинете и попробуйте ещё раз."
        )
        return
    await callback.answer("Кабинет проверен")
    await callback.message.answer(  # type: ignore[union-attr]
        "Кабинет проверен. Можно собирать реальные дела."
    )


@router.callback_query(F.data.startswith("account:sync:"))
async def sync_account(callback: CallbackQuery) -> None:
    account_id = callback.data.split(":")[-1] if callback.data else ""
    ctx = await user_context(callback)
    try:
        async with get_sessionmaker()() as session:
            result = await sync_ozon_catalog_for_account(session, ctx, account_id)
        await callback.answer("Данные обновлены")
        await callback.message.answer(  # type: ignore[union-attr]
            f"Обновил каталог: {int(result['count'])} товаров."
        )
    except ValueError:
        async with get_sessionmaker()() as session:
            await plan_catalog_sync_for_account(session, ctx, account_id)
        await callback.answer("План готов")
        await callback.message.answer(  # type: ignore[union-attr]
            "Подготовил безопасную проверку обновления. "
            "Живое обновление включим после проверки API."
        )
    except Exception:
        await callback.answer("Не получилось обновить", show_alert=True)
        await callback.message.answer(  # type: ignore[union-attr]
            "Кабинет пока не отдал данные. Ничего не изменил."
        )


@router.callback_query(F.data.startswith("task:delay:"))
async def delay_task(callback: CallbackQuery) -> None:
    await callback.answer("Отложил")
    await callback.message.answer("Ок. Верну это дело позже.")  # type: ignore[union-attr]
