"""Modelos SQLAlchemy 2.0 com entidade base."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from infra.config import settings


def new_uuid7() -> str:
    return str(uuid.uuid7())


class Base(DeclarativeBase):
    metadata = MetaData(schema=settings.db_schema or None)


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


class PlayerLocalStats(TimestampMixin, Base):
    """Estatísticas locais acumuladas por jogador."""

    __tablename__ = "player_local_stats"

    player: Mapped[str] = mapped_column(String(100), primary_key=True)
    matches_played: Mapped[int] = mapped_column(Integer, default=0)
    goals_for: Mapped[int] = mapped_column(Integer, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def avg_goals_for(self) -> float:
        return self.goals_for / self.matches_played if self.matches_played else 0.0

    @property
    def avg_goals_against(self) -> float:
        return self.goals_against / self.matches_played if self.matches_played else 0.0


class Prediction(TimestampMixin, Base):
    """Palpite gerado pelo bot."""

    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid7)
    match_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    kickoff_brt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    home_team: Mapped[str] = mapped_column(String(100))
    home_player: Mapped[str] = mapped_column(String(100))
    away_team: Mapped[str] = mapped_column(String(100))
    away_player: Mapped[str] = mapped_column(String(100))
    expected_total_goals: Mapped[float] = mapped_column(Float)
    over_line: Mapped[float] = mapped_column(Float)
    message_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    home_goals: Mapped[int | None] = mapped_column(Integer, default=None)
    away_goals: Mapped[int | None] = mapped_column(Integer, default=None)
    success: Mapped[bool | None] = mapped_column(Boolean, default=None)
