from httpx import ASGITransport, AsyncClient

from operator_day.bot.keyboards import accounts_keyboard, main_menu
from operator_day.config import get_settings
from operator_day.domain import ConnectedAccount, Platform
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
