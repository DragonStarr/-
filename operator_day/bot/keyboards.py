from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from operator_day.config import get_settings
from operator_day.domain import ConnectedAccount, TaskAction


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Дела"), KeyboardButton(text="Кабинеты")],
            [KeyboardButton(text="Финансы"), KeyboardButton(text="ПВЗ")],
            [KeyboardButton(text="Настройки")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите кнопку",
    )


def miniapp_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть экран",
                    web_app=WebAppInfo(url=get_settings().miniapp_public_url),
                )
            ]
        ]
    )


def task_keyboard(task: TaskAction) -> InlineKeyboardMarkup:
    primary = task.action_label
    if task.confidence < 0.5:
        primary = "Проверить"
    buttons = [[InlineKeyboardButton(text=primary, callback_data=f"task:confirm:{task.task_id}")]]
    buttons.append(
        [
            InlineKeyboardButton(text="Показать", callback_data=f"task:show:{task.task_id}"),
            InlineKeyboardButton(text="Отложить", callback_data=f"task:delay:{task.task_id}"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def accounts_keyboard(accounts: list[ConnectedAccount]) -> InlineKeyboardMarkup | None:
    if not accounts:
        return None
    buttons = []
    for account in accounts:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="Проверить кабинет",
                    callback_data=f"account:validate:{account.account_id}",
                ),
                InlineKeyboardButton(
                    text="Обновить данные",
                    callback_data=f"account:sync:{account.account_id}",
                ),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)
