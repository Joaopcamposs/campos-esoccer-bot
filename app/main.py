"""Ponto de entrada — FastAPI com lifespan e webhook Telegram."""

import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

import app.jobs
from app.scheduler import start_all, stop_all
from app.telegram import client
from app.telegram.handler import handle_update
from app.telegram.polling import polling_loop
from app.telegram.service import edit_by_reference, list_pending, send_and_store
from infra.config import settings
from infra.database import engine, get_session
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


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check."""
    return {"status": "healthy"}


@app.post("/api/send")
async def api_send(
    text: str,
    reference_key: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Endpoint exemplo: envia mensagem ao canal configurado."""
    record = await send_and_store(
        session,
        settings.telegram_channel_id,
        text,
        reference_key=reference_key,
    )
    return {
        "message_id": record.message_id,
        "reference_key": record.reference_key,
        "status": record.status,
    }


@app.get("/api/pending")
async def api_pending(
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Lista mensagens pendentes de atualização."""
    records = await list_pending(session)
    return [
        {
            "id": r.id,
            "chat_id": r.chat_id,
            "message_id": r.message_id,
            "reference_key": r.reference_key,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@app.post("/api/demo")
async def api_demo(
    initial_text: str = "⏳ Carregando dados...",
    final_text: str = "✅ Dados carregados com sucesso!",
    delay: int = 3,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Demo: envia mensagem, espera N segundos e edita. Fluxo completo de scraping."""
    ref_key = f"demo-{__import__('uuid').uuid7()}"

    record = await send_and_store(
        session,
        settings.telegram_channel_id,
        initial_text,
        reference_key=ref_key,
    )
    logger.info("Demo: enviado ref=%s msg_id=%s", ref_key, record.message_id)

    await asyncio.sleep(min(delay, 10))

    result = await edit_by_reference(session, ref_key, final_text)
    logger.info("Demo: editado ref=%s", ref_key)

    return {
        "reference_key": ref_key,
        "message_id": record.message_id,
        "initial_text": initial_text,
        "final_text": final_text,
        "delay": delay,
        "status": "done" if result else "error",
    }


@app.put("/api/edit")
async def api_edit(
    reference_key: str,
    text: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Endpoint exemplo: edita mensagem por reference_key."""
    result = await edit_by_reference(session, reference_key, text)
    if not result:
        raise HTTPException(404, "Message not found")
    return {"status": "edited"}
