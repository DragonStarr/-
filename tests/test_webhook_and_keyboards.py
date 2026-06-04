from httpx import ASGITransport, AsyncClient

from operator_day.bot import handlers
from operator_day.bot.keyboards import accounts_keyboard, main_menu
from operator_day.config import get_settings
from operator_day.connectors.transport import MarketplaceApiError
from operator_day.domain import (
    ActionResult,
    ActionRisk,
    ConnectedAccount,
    ModuleId,
    Platform,
    Role,
    TaskAction,
    TaskStatus,
    TenantContext,
)
from operator_day.main import create_app


def test_main_menu_is_button_first_without_commands() -> None:
    keyboard = main_menu()
    labels = [button.text for row in keyboard.keyboard for button in row]

    assert labels == ["Дела", "Кабинеты", "Финансы", "ПВЗ", "Настройки"]
    assert not any(label.startswith("/") for label in labels)


def test_accounts_keyboard_has_plain_action_buttons() -> None:
    keyboard = accounts_keyboard(
        [
            ConnectedAccount(
                account_id="account-1",
                platform=Platform.OZON,
                title="Ozon",
                status="ready_for_validation",
                token_fingerprint="abc123",
                capabilities={"catalog": "ready"},
            )
        ]
    )

    assert keyboard is not None
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert labels == ["Проверить кабинет", "Обновить данные"]
    assert not any("/" in label for label in labels)


async def test_telegram_webhook_rejects_wrong_secret(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "expected-secret")
    get_settings.cache_clear()
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
            json={"update_id": 1},
        )

    get_settings.cache_clear()
    assert response.status_code == 403


async def test_telegram_webhook_skips_without_bot_token(monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "expected-secret")
    get_settings.cache_clear()
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
            json={"update_id": 1},
        )

    get_settings.cache_clear()
    assert response.status_code == 200
    assert response.json()["status"] == "skipped"


async def test_bot_confirm_masks_marketplace_failure_without_saving(monkeypatch) -> None:
    task = TaskAction(
        module_id=ModuleId.REVIEWS,
        title="Ответить на отзыв",
        short_text="Подготовить ответ",
        action_label="Ответить",
        payload={"review_id": "review-1"},
        priority=5,
        risk=ActionRisk.CONFIRM,
    )
    saved: list[str] = []

    class FakeOrchestratorCache:
        def get_task(self, task_id: str):
            raise KeyError(task_id)

    class FakeMorningOrchestrator:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def execute_prepared(self, ctx, task):
            raise MarketplaceApiError("leaked-internal-marketplace-error")

    class FakeRepo:
        def __init__(self, session) -> None:
            pass

        async def get_execution(self, ctx, task_id, idempotency_key):
            return None

        async def get_task(self, ctx, task_id):
            return task

        async def save_result(self, ctx, task, result, *, idempotency_key: str):
            saved.append(idempotency_key)

    class FakeSessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeMessage:
        def __init__(self) -> None:
            self.answers: list[str] = []

        async def answer(self, text: str, **kwargs) -> None:
            self.answers.append(text)

    class FakeCallback:
        data = "task:confirm:task-1"

        def __init__(self) -> None:
            self.message = FakeMessage()
            self.answers: list[tuple[str, bool | None]] = []

        async def answer(self, text: str, show_alert: bool | None = None) -> None:
            self.answers.append((text, show_alert))

    async def fake_user_context(callback):
        return TenantContext(tenant_id="bot-failure", user_id="owner", role=Role.OWNER)

    monkeypatch.setattr(
        handlers,
        "user_context",
        fake_user_context,
    )
    monkeypatch.setattr(handlers, "get_sessionmaker", lambda: lambda: FakeSessionContext())
    monkeypatch.setattr(handlers, "orchestrator", FakeOrchestratorCache())
    monkeypatch.setattr(handlers, "MorningOrchestrator", FakeMorningOrchestrator)
    monkeypatch.setattr(handlers, "TaskRepository", FakeRepo)

    callback = FakeCallback()
    await handlers.confirm_task(callback)  # type: ignore[arg-type]

    assert saved == []
    assert callback.answers == [("Кабинет не принял действие", True)]
    assert "leaked-internal-marketplace-error" not in callback.message.answers[0]
    assert "ничего не изменили" in callback.message.answers[0].lower()


async def test_bot_confirm_reuses_existing_execution_without_repeating_action(monkeypatch) -> None:
    calls: list[str] = []
    existing = ActionResult(
        task_id="task-1",
        status=TaskStatus.DONE,
        user_text="Уже записано раньше.",
        audit_event={"action": "already_done"},
    )

    class FakeOrchestratorCache:
        def get_task(self, task_id: str):
            calls.append("get_task")
            raise KeyError(task_id)

    class FakeMorningOrchestrator:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def execute_prepared(self, ctx, task):
            calls.append("execute")
            raise AssertionError("should not execute twice")

    class FakeRepo:
        def __init__(self, session) -> None:
            pass

        async def get_execution(self, ctx, task_id, idempotency_key):
            return existing

        async def get_task(self, ctx, task_id):
            calls.append("repo_get_task")
            return None

        async def save_result(self, ctx, task, result, *, idempotency_key: str):
            calls.append("save")

    class FakeSessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeMessage:
        def __init__(self) -> None:
            self.answers: list[str] = []

        async def answer(self, text: str, **kwargs) -> None:
            self.answers.append(text)

    class FakeCallback:
        data = "task:confirm:task-1"

        def __init__(self) -> None:
            self.message = FakeMessage()
            self.answers: list[tuple[str, bool | None]] = []

        async def answer(self, text: str, show_alert: bool | None = None) -> None:
            self.answers.append((text, show_alert))

    async def fake_user_context(callback):
        return TenantContext(tenant_id="bot-idempotent", user_id="owner", role=Role.OWNER)

    monkeypatch.setattr(handlers, "user_context", fake_user_context)
    monkeypatch.setattr(handlers, "get_sessionmaker", lambda: lambda: FakeSessionContext())
    monkeypatch.setattr(handlers, "orchestrator", FakeOrchestratorCache())
    monkeypatch.setattr(handlers, "MorningOrchestrator", FakeMorningOrchestrator)
    monkeypatch.setattr(handlers, "TaskRepository", FakeRepo)

    callback = FakeCallback()
    await handlers.confirm_task(callback)  # type: ignore[arg-type]

    assert calls == []
    assert callback.answers == [("Уже записано", None)]
    assert callback.message.answers == ["Уже записано раньше."]
