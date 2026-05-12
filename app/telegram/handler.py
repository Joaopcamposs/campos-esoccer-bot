"""Handler de webhook/polling — processa updates do Telegram."""

import logging
from typing import Any

from app.telegram import client

logger = logging.getLogger(__name__)


async def handle_update(update: dict[str, Any]) -> None:
    """Processa um update recebido via webhook ou polling."""
    message = update.get("message")
    if not message:
        logger.debug("Update sem message: %s", update.get("update_id"))
        return

    chat_id = message["chat"]["id"]
    chat_type = message["chat"].get("type", "unknown")
    username = message.get("from", {}).get("username", "unknown")
    text = message.get("text", "")

    logger.info(
        "Update recebido: chat_id=%s type=%s user=%s text='%s'",
        chat_id,
        chat_type,
        username,
        text[:50],
    )

    if text.startswith("/start"):
        await client.send_message(chat_id, "Bot ativo.")
        return

    if text.startswith("/ping"):
        await client.send_message(chat_id, "pong")
        return

    await client.send_message(
        chat_id,
        "Bot operando em modo automático. Comandos: /start /ping",
    )
