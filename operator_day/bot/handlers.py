from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from operator_day.bot.keyboards import accounts_keyboard, main_menu, task_keyboard
from operator_day.bot.render import render_accounts_status, render_task, render_welcome
from operator_day.brain.orchestrator import MorningOrchestrator
from operator_day.connectors.live_sync import (
    plan_catalog_sync_for_account,
    sync_ozon_catalog_for_account,
    validate_account_for_read_access,
)
from operator_day.connectors.replay import DatabaseReplayHub
from operator_day.db import ensure_local_database, get_sessionmaker
from operator_day.domain import TenantContext
from operator_day.repositories import AccountRepository, TaskRepository, UserRepository

router = Router()
orchestrator = MorningOrchestrator()


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


@router.message(F.text == "Дела")
async def morning(message: Message) -> None:
    ctx = await user_context(message)
    async with get_sessionmaker()() as session:
        tasks = await MorningOrchestrator(replay=DatabaseReplayHub(session, ctx)).morning_top(ctx)
        await TaskRepository(session).save_tasks(ctx, tasks)
    await message.answer(f"Нашел {len(tasks)} главных дел.", reply_markup=main_menu())
    for task in tasks:
        await message.answer(render_task(task), reply_markup=task_keyboard(task))


@router.message(F.text == "Кабинеты")
async def accounts(message: Message) -> None:
    ctx = await user_context(message)
    async with get_sessionmaker()() as session:
        rows = await AccountRepository(session).list_accounts(ctx)
    await message.answer(
        render_accounts_status(rows),
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
    for task in tasks:
        await message.answer(render_task(task), reply_markup=task_keyboard(task))


@router.message(F.text == "Настройки")
async def settings(message: Message) -> None:
    await message.answer(
        "Пилотный режим включен. Реальные токены кабинетов пока не подключены.",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data.startswith("task:confirm:"))
async def confirm_task(callback: CallbackQuery) -> None:
    task_id = callback.data.split(":")[-1] if callback.data else ""
    ctx = await user_context(callback)
    async with get_sessionmaker()() as session:
        repo = TaskRepository(session)
        try:
            task = orchestrator.get_task(task_id)
        except KeyError:
            task = await repo.get_task(ctx, task_id)
        if task is None:
            await callback.answer("Дело уже не найдено", show_alert=True)
            return
        result = await MorningOrchestrator(
            replay=DatabaseReplayHub(session, ctx)
        ).execute_prepared(ctx, task)
        await TaskRepository(session).save_result(ctx, task, result, idempotency_key=task_id)
    await callback.answer("Записал")
    await callback.message.answer(result.user_text)  # type: ignore[union-attr]


@router.callback_query(F.data.startswith("task:show:"))
async def show_task(callback: CallbackQuery) -> None:
    task_id = callback.data.split(":")[-1] if callback.data else ""
    ctx = await user_context(callback)
    async with get_sessionmaker()() as session:
        try:
            task = orchestrator.get_task(task_id)
        except KeyError:
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
            "Не получилось проверить кабинет. Проверь ключ в личном кабинете и попробуй ещё раз."
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
            "Подготовил проверку обновления. "
            "Живое обновление для этой площадки включим после проверки API."
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
