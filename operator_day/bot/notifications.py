from __future__ import annotations

from aiogram import Bot

from operator_day.bot.keyboards import main_menu
from operator_day.bot.render import render_morning
from operator_day.domain import TaskAction


async def send_morning_digest(bot: Bot, chat_id: str, tasks: list[TaskAction]) -> None:
    if not tasks:
        return
    await bot.send_message(
        chat_id=chat_id,
        text=render_morning(tasks),
        reply_markup=main_menu(),
        disable_notification=False,
    )
