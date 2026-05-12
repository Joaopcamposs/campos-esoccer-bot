"""Testes de configuração."""

from infra.config import Settings


def test_settings_defaults():
    """Verifica valores padrão da configuração."""
    s = Settings(
        telegram_bot_token="",
        telegram_webhook_secret="",
        telegram_channel_id=0,
        database_url="postgresql+asyncpg://app:app@localhost:5432/app",
    )
    assert s.webhook_path == "/webhook/telegram"
    assert s.database_url.startswith("postgresql")
