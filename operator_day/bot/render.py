from __future__ import annotations

from operator_day.domain import ActionRisk, TaskAction


def render_welcome() -> str:
    return (
        "Я Оператор дня. Соберу главные дела по кабинетам и ПВЗ. "
        "Ничего опасного не делаю без кнопки ОК."
    )


def render_task(task: TaskAction) -> str:
    prefix = "Проверь" if task.risk in {ActionRisk.CONFIRM, ActionRisk.HUMAN} else "Готово"
    lines = [f"{prefix}: {task.title}", "", task.short_text]
    if task.money_effect:
        lines.append(f"Ожидаемый эффект: около {int(task.money_effect)} ₽.")
    if task.deadline_at:
        lines.append("Есть срок. Лучше не откладывать.")
    if task.confidence < 0.5:
        lines.append("Данных мало. Я подготовил черновик, но его нужно проверить.")
    return "\n".join(lines)


def render_morning(tasks: list[TaskAction]) -> str:
    lines = ["Главные дела на сегодня:"]
    for index, task in enumerate(tasks, start=1):
        lines.append(f"{index}. {task.title} - {task.short_text}")
    return "\n".join(lines)


def render_accounts_status(accounts) -> str:
    if not accounts:
        return (
            "Кабинеты пока не подключены.\n"
            "Подключи кабинет WB, Ozon или Яндекс Маркета, и я начну собирать реальные дела."
        )
    lines = ["Кабинеты:"]
    for account in accounts:
        lines.append(account.title)
        for name, status in account.capabilities.items():
            label = _capability_label(name, status)
            if label:
                lines.append(f"• {label}")
    return "\n".join(lines)


def _capability_label(name: str, status: str) -> str:
    readable = {
        "catalog": "Каталог",
        "reviews": "Отзывы",
        "finance": "Финансы",
        "ads": "Реклама",
        "claims": "Претензии",
        "pvz": "ПВЗ",
    }.get(name, name)
    if status == "ready":
        return f"{readable} готов"
    if status == "needs_credentials":
        return f"{readable} ждёт ключ"
    if status == "needs_api_verification":
        return f"{readable} нужно проверить в кабинете"
    return ""
