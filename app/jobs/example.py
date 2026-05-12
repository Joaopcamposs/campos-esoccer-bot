"""Job exemplo — modelo de implementação para rotinas periódicas."""

import logging

from scheduler import register

logger = logging.getLogger(__name__)


@register("example-heartbeat", interval_seconds=300)
async def heartbeat():
    """Rotina exemplo executada a cada 5 minutos.

    Substitua pelo seu scraping/notificação.
    Exemplo real:
        async with async_session() as session:
            data = await scrape_something()
            await send_and_store(session, chat_id, data, reference_key="my-ref")
    """
    logger.info("Heartbeat: job exemplo executado")
