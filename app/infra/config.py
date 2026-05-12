"""Configuração central da aplicação via variáveis de ambiente."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_channel_id: int = 0
    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/app"
    webhook_path: str = "/webhook/telegram"
    telegram_polling: bool = True
    log_level: str = "INFO"


settings = Settings()
