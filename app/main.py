"""Ponto de entrada — FastAPI com lifespan e webhook Telegram."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from typing import Any

import jobs  # noqa: F401
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from routes import router as aux_routes
from scheduler import start_all, stop_all
from telegram import client
from telegram.handler import handle_update
from telegram.polling import polling_loop

from infra.config import settings
from infra.database import engine
from infra.models import Base

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_polling_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa banco, inicia scheduler/polling e fecha conexões no shutdown."""
    global _polling_task

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Banco inicializado")

    start_all()

    if settings.telegram_polling:
        _polling_task = asyncio.create_task(polling_loop())
        logger.info("Polling mode ativado")
    else:
        logger.info("Webhook mode — polling desativado")

    yield

    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
        logger.info("Polling encerrado")

    await stop_all()
    await client.close_client()
    await engine.dispose()
    logger.info("Shutdown completo")


app = FastAPI(title="FastAPI Telegram Base", lifespan=lifespan)
app.include_router(aux_routes)


def verify_secret(x_telegram_bot_api_secret_token: str | None = Header(None)):
    """Valida secret token do webhook Telegram."""
    if not settings.telegram_webhook_secret:
        return
    if not x_telegram_bot_api_secret_token:
        raise HTTPException(403, "Missing secret token")
    if not hmac.compare_digest(
        x_telegram_bot_api_secret_token, settings.telegram_webhook_secret
    ):
        raise HTTPException(403, "Invalid secret token")


@app.post(settings.webhook_path, dependencies=[Depends(verify_secret)])
async def telegram_webhook(request: Request) -> dict[str, str]:
    """Recebe updates do Telegram via webhook."""
    update: dict[str, Any] = await request.json()
    logger.info("Webhook update recebido: %s", update.get("update_id"))
    await handle_update(update)
    return {"status": "ok"}
