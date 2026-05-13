"""Cliente HTTP leve para Telegram Bot API com retry básico."""

import asyncio
import logging
from typing import Any

import httpx

from infra.config import settings

logger = logging.getLogger(__name__)

BASE_URL = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

_http_client: httpx.AsyncClient | None = None

MAX_RETRIES = 3


def get_client() -> httpx.AsyncClient:
    """Retorna client HTTP singleton (reutiliza conexões)."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=httpx.Timeout(10.0, read=60.0),
        )
    return _http_client


async def close_client() -> None:
    """Fecha client HTTP."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None
        logger.info("HTTP client fechado")


async def api_call(method: str, **kwargs: Any) -> dict[str, Any]:
    """Chamada à Telegram Bot API com retry em 429 (rate limit)."""
    client = get_client()
    for attempt in range(MAX_RETRIES):
        response = await client.post(f"/{method}", json=kwargs)
        if response.status_code == 429:
            retry_after = response.json().get("parameters", {}).get("retry_after", 1)
            logger.warning("Rate limit 429 em %s, retry em %ss", method, retry_after)
            await asyncio.sleep(retry_after)
            continue
        if response.status_code >= 400:
            body = (
                response.json()
                if response.headers.get("content-type", "").startswith("application/json")
                else response.text
            )
            logger.error("Telegram API %s → %s: %s", method, response.status_code, body)
        response.raise_for_status()
        logger.debug("API %s → %s", method, response.status_code)
        return response.json()
    response.raise_for_status()
    return response.json()


async def send_message(chat_id: int, text: str, **kwargs: Any) -> dict[str, Any]:
    """Envia mensagem de texto com parse_mode HTML por padrão."""
    kwargs.setdefault("parse_mode", "HTML")
    logger.info("Enviando mensagem para chat_id=%s", chat_id)
    return await api_call("sendMessage", chat_id=chat_id, text=text, **kwargs)


async def edit_message_text(
    chat_id: int, message_id: int, text: str, **kwargs: Any
) -> dict[str, Any]:
    """Edita texto de mensagem existente."""
    kwargs.setdefault("parse_mode", "HTML")
    logger.info("Editando mensagem %s em chat_id=%s", message_id, chat_id)
    return await api_call(
        "editMessageText",
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        **kwargs,
    )


async def send_photo(
    chat_id: int, photo: str, caption: str | None = None, **kwargs: Any
) -> dict[str, Any]:
    """Envia foto via URL ou file_id."""
    kwargs.setdefault("parse_mode", "HTML")
    logger.info("Enviando foto para chat_id=%s", chat_id)
    params: dict[str, Any] = {"chat_id": chat_id, "photo": photo, **kwargs}
    if caption:
        params["caption"] = caption
    return await api_call("sendPhoto", **params)


async def edit_message_media(
    chat_id: int, message_id: int, media: dict[str, Any], **kwargs: Any
) -> dict[str, Any]:
    """Edita mídia de mensagem existente."""
    logger.info("Editando mídia %s em chat_id=%s", message_id, chat_id)
    return await api_call(
        "editMessageMedia",
        chat_id=chat_id,
        message_id=message_id,
        media=media,
        **kwargs,
    )


async def get_updates(offset: int | None = None, timeout: int = 30) -> list[dict]:
    """Busca updates via long polling."""
    params: dict[str, Any] = {"timeout": timeout}
    if offset:
        params["offset"] = offset
    result = await api_call("getUpdates", **params)
    return result.get("result", [])


async def delete_webhook() -> None:
    """Remove webhook para usar polling."""
    await api_call("deleteWebhook")
    logger.info("Webhook removido para polling mode")
