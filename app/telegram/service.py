"""Serviço de alto nível para envio/edição com persistência."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.telegram import client
from infra.models import SentMessage

logger = logging.getLogger(__name__)


async def send_and_store(
    session: AsyncSession,
    chat_id: int,
    text: str,
    reference_key: str | None = None,
    **kwargs,
) -> SentMessage:
    """Envia mensagem e armazena message_id para edição futura."""
    result = await client.send_message(chat_id, text, **kwargs)
    msg_id = result["result"]["message_id"]

    record = SentMessage(
        chat_id=chat_id,
        message_id=msg_id,
        content_type="text",
        status="pending",
        reference_key=reference_key,
    )
    session.add(record)
    await session.commit()
    logger.info(
        "Mensagem armazenada: id=%s msg_id=%s ref=%s",
        record.id,
        msg_id,
        reference_key,
    )
    return record


async def edit_by_reference(
    session: AsyncSession,
    reference_key: str,
    text: str,
    **kwargs,
) -> dict | None:
    """Edita mensagem usando reference_key como localizador e marca como done."""
    stmt = (
        select(SentMessage)
        .where(SentMessage.reference_key == reference_key)
        .order_by(SentMessage.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        logger.warning("Referência não encontrada: %s", reference_key)
        return None

    api_result = await client.edit_message_text(
        record.chat_id, record.message_id, text, **kwargs
    )
    record.status = "done"
    await session.commit()
    logger.info("Mensagem editada: ref=%s status=done", reference_key)
    return api_result


async def mark_error(
    session: AsyncSession,
    reference_key: str,
    detail: str,
) -> SentMessage | None:
    """Marca mensagem como erro e registra detalhe."""
    stmt = (
        select(SentMessage)
        .where(SentMessage.reference_key == reference_key)
        .order_by(SentMessage.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        return None

    record.status = "error"
    record.error_detail = detail
    await session.commit()
    logger.error("Mensagem com erro: ref=%s detail=%s", reference_key, detail)
    return record


async def list_pending(session: AsyncSession) -> list[SentMessage]:
    """Lista mensagens com status pending."""
    stmt = (
        select(SentMessage)
        .where(SentMessage.status == "pending")
        .order_by(SentMessage.created_at.asc())
    )
    result = await session.execute(stmt)
    records = list(result.scalars().all())
    logger.debug("Pendentes encontrados: %d", len(records))
    return records


async def send_photo_and_store(
    session: AsyncSession,
    chat_id: int,
    photo: str,
    caption: str | None = None,
    reference_key: str | None = None,
    **kwargs,
) -> SentMessage:
    """Envia foto e armazena para edição futura."""
    result = await client.send_photo(chat_id, photo, caption, **kwargs)
    msg_id = result["result"]["message_id"]

    record = SentMessage(
        chat_id=chat_id,
        message_id=msg_id,
        content_type="photo",
        status="pending",
        reference_key=reference_key,
    )
    session.add(record)
    await session.commit()
    logger.info(
        "Foto armazenada: id=%s msg_id=%s ref=%s",
        record.id,
        msg_id,
        reference_key,
    )
    return record
