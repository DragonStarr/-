from operator_day.bot.render import render_accounts_status
from operator_day.domain import ConnectedAccount, Platform


def test_render_accounts_status_without_accounts_is_plain() -> None:
    text = render_accounts_status([])

    assert "replay" not in text.lower()
    assert "Подключи кабинет" in text
    assert "/" not in text


def test_render_accounts_status_with_account_shows_simple_capabilities() -> None:
    account = ConnectedAccount(
        account_id="a1",
        platform=Platform.OZON,
        title="Ozon основной",
        status="ready",
        token_fingerprint="abc123",
        capabilities={"catalog": "ready", "ads": "needs_credentials"},
    )

    text = render_accounts_status([account])

    assert "Ozon основной" in text
    assert "Каталог готов" in text
    assert "Реклама ждёт ключ" in text
