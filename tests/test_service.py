"""Testes do serviço de envio/edição com persistência."""

from sqlalchemy import select

from app.telegram.service import (
    edit_by_reference,
    list_pending,
    mark_error,
    send_and_store,
    send_photo_and_store,
)
from infra.models import SentMessage


async def test_send_and_store(db_session, mock_telegram):
    """Verifica envio e armazenamento."""
    record = await send_and_store(db_session, 123, "test", reference_key="ref-1")
    assert record.message_id == 42
    assert record.reference_key == "ref-1"
    assert record.status == "pending"

    result = await db_session.execute(select(SentMessage))
    assert result.scalar_one().chat_id == 123


async def test_edit_by_reference(db_session, mock_telegram):
    """Verifica edição por reference_key e transição de status."""
    record = await send_and_store(db_session, 123, "original", reference_key="ref-edit")
    assert record.status == "pending"

    result = await edit_by_reference(db_session, "ref-edit", "updated")
    assert result is not None
    assert result["ok"] is True

    await db_session.refresh(record)
    assert record.status == "done"


async def test_edit_by_reference_not_found(db_session, mock_telegram):
    """Verifica retorno None para referência inexistente."""
    result = await edit_by_reference(db_session, "nonexistent", "text")
    assert result is None


async def test_mark_error(db_session, mock_telegram):
    """Verifica marcação de erro com detalhe."""
    await send_and_store(db_session, 123, "test", reference_key="ref-err")
    record = await mark_error(db_session, "ref-err", "timeout na API")
    assert record is not None
    assert record.status == "error"
    assert record.error_detail == "timeout na API"


async def test_mark_error_not_found(db_session, mock_telegram):
    """Verifica retorno None para referência inexistente."""
    result = await mark_error(db_session, "nope", "erro")
    assert result is None


async def test_list_pending(db_session, mock_telegram):
    """Verifica listagem de mensagens pendentes."""
    await send_and_store(db_session, 123, "a", reference_key="ref-a")
    await send_and_store(db_session, 123, "b", reference_key="ref-b")
    await edit_by_reference(db_session, "ref-a", "done")

    pending = await list_pending(db_session)
    assert len(pending) == 1
    assert pending[0].reference_key == "ref-b"


async def test_send_photo_and_store(db_session, mock_telegram):
    """Verifica envio de foto com armazenamento."""
    record = await send_photo_and_store(
        db_session, 123, "https://example.com/img.jpg", "caption", "ref-photo"
    )
    assert record.content_type == "photo"
    assert record.message_id == 42
