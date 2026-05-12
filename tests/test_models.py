"""Testes dos modelos SQLAlchemy."""

from sqlalchemy import select

from infra.models import SentMessage


async def test_create_sent_message(db_session):
    """Verifica criação e persistência de SentMessage."""
    msg = SentMessage(
        chat_id=123456,
        message_id=789,
        content_type="text",
        reference_key="test-ref",
    )
    db_session.add(msg)
    await db_session.commit()

    result = await db_session.execute(
        select(SentMessage).where(SentMessage.reference_key == "test-ref")
    )
    record = result.scalar_one()
    assert record.chat_id == 123456
    assert record.message_id == 789
    assert record.content_type == "text"
    assert record.status == "pending"


async def test_sent_message_nullable_reference(db_session):
    """Verifica que reference_key pode ser None."""
    msg = SentMessage(chat_id=111, message_id=222)
    db_session.add(msg)
    await db_session.commit()

    result = await db_session.execute(select(SentMessage).where(SentMessage.chat_id == 111))
    record = result.scalar_one()
    assert record.reference_key is None
