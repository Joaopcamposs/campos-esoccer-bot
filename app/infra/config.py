"""Configuração central da aplicação via variáveis de ambiente."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_channel_id: int = 0
    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/app"

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "sslmode=" in url:
            url = url.split("?")[0]
        return url

    webhook_path: str = "/webhook/telegram"
    telegram_polling: bool = True
    log_level: str = "INFO"
    aceodds_timezone: str = "America/Sao_Paulo"
    totalcorner_timezone: str = "Europe/London"
    db_schema: str = "esoccer_bot"


settings = Settings()
