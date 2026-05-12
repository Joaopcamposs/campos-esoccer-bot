"""Polling mode para desenvolvimento local sem webhook."""

import asyncio
import logging

from telegram import client
from telegram.handler import handle_update

logger = logging.getLogger(__name__)


async def polling_loop() -> None:
    """Long polling — busca updates e processa."""
    await client.delete_webhook()
    logger.info("Polling mode iniciado")

    offset = None
    while True:
        try:
            updates = await client.get_updates(offset=offset, timeout=30)
            for update in updates:
                offset = update["update_id"] + 1
                logger.debug("Processando update_id=%s", update["update_id"])
                await handle_update(update)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Erro no polling loop")
            await asyncio.sleep(3)
