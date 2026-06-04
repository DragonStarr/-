from __future__ import annotations

from operator_day.domain import ActionRisk, Platform, TaskAction


def render_welcome() -> str:
    return (
        "Я Оператор дня. Соберу главные дела по кабинетам и ПВЗ. "
        "Ничего опасного не делаю без кнопки ОК."
    )


def render_task(task: TaskAction) -> str:
    prefix = "Проверь" if task.risk in {ActionRisk.CONFIRM, ActionRisk.HUMAN} else "Есть дело"
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


def render_accounts_status(
    accounts,
    *,
    live_blockers: list[str] | tuple[str, ...] = (),
    write_scope_blockers: list[str] | tuple[str, ...] = (),
) -> str:
    if not accounts:
        return (
            "Кабинеты пока не подключены.\n"
            "Подключите WB, Ozon или Яндекс Маркет, и я начну собирать реальные дела."
        )
    lines = ["Кабинеты:"]
    for account in accounts:
        lines.append(account.title)
        for name, status in account.capabilities.items():
            label = _capability_label(name, status)
            if label:
                lines.append(f"- {label}")
    if write_scope_blockers:
        lines.append("")
        lines.append(
            "Для живых действий осталось проверить: "
            + ", ".join(_write_scope_label(item) for item in write_scope_blockers)
            + "."
        )
    if live_blockers:
        labels = [_live_blocker_label(item) for item in live_blockers if item]
        if labels:
            lines.append("")
            lines.append("Живая работа пока ждёт: " + ", ".join(labels) + ".")
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
        return f"{readable} нужно проверить"
    return ""


def _write_scope_label(value: str) -> str:
    platform, _, scope = value.partition(":")
    scope_map = {
        "catalog": "цены и карточки",
        "reviews": "ответы покупателям",
        "ads": "реклама",
    }
    return f"{_platform_label(platform)} — {scope_map.get(scope, scope or 'действие')}"


def _platform_label(value: str) -> str:
    labels = {
        Platform.WB.value: "Wildberries",
        Platform.OZON.value: "Ozon",
        Platform.YANDEX.value: "Яндекс Маркет",
        Platform.PVZ.value: "ПВЗ",
    }
    return labels.get(value, value)


def _live_blocker_label(value: str) -> str:
    labels = {
        "marketplace_api_verification": "проверку кабинета",
        "marketplace_write_scope_verification": "права на реальные действия",
        "claim_deadline_policies": "сроки претензий с источником",
        "prod_llm_gate": "проверку модели на сервере",
    }
    return labels.get(value, value)
