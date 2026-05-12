"""Modelos SQLAlchemy 2.0 com entidade base."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_uuid7() -> str:
    return str(uuid.uuid7())


class Base(DeclarativeBase):
    """Entidade base com campos padrão."""


class TimestampMixin:
    """Mixin com timestamps automáticos."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SentMessage(TimestampMixin, Base):
    """Armazena mensagens enviadas para possibilitar edição posterior."""

    __tablename__ = "sent_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid7)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger)
    content_type: Mapped[str] = mapped_column(default="text")
    status: Mapped[str] = mapped_column(default="pending")
    error_detail: Mapped[str | None] = mapped_column(default=None)
    reference_key: Mapped[str | None] = mapped_column(index=True, default=None)
