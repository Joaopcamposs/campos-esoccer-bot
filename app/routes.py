"""Rotas API — endpoints de negócio."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.scrapers.aceodds import fetch_upcoming_matches
from app.scrapers.totalcorner import fetch_goal_stats, fetch_player_stats
from app.telegram.service import edit_by_reference, list_pending, send_and_store
from infra.config import settings
from infra.database import get_session

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check."""
    return {"status": "healthy"}


@router.post("/send")
async def api_send(
    text: str,
    reference_key: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Envia mensagem ao canal configurado."""
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


@router.get("/pending")
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


@router.get("/upcoming")
async def api_upcoming(window: int = 10) -> dict[str, Any]:
    """Jogos eSoccer Battle nos próximos N minutos (BRT)."""
    matches = await fetch_upcoming_matches(window_minutes=window)
    return {
        "count": len(matches),
        "window_minutes": window,
        "matches": [m.to_dict() for m in matches],
    }


@router.get("/player-stats")
async def api_player_stats(
    player: str | None = None,
) -> dict[str, Any]:
    """Estatísticas consolidadas de jogadores (totalcorner, últimas 48h)."""
    stats = await fetch_player_stats()
    if player:
        stats = [s for s in stats if player.lower() in s.player.lower()]
    return {
        "count": len(stats),
        "players": [s.to_dict() for s in stats],
    }


@router.get("/goal-stats")
async def api_goal_stats(
    player: str | None = None,
) -> dict[str, Any]:
    """Estatísticas de gols e porcentagens over (totalcorner, últimas 48h)."""
    stats = await fetch_goal_stats()
    if player:
        stats = [s for s in stats if player.lower() in s.player.lower()]
    return {
        "count": len(stats),
        "players": [s.to_dict() for s in stats],
    }


@router.put("/edit")
async def api_edit(
    reference_key: str,
    text: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Edita mensagem por reference_key."""
    result = await edit_by_reference(session, reference_key, text)
    if not result:
        raise HTTPException(404, "Message not found")
    return {"status": "edited"}


@router.post("/demo")
async def api_demo(
    initial_text: str = "⏳ Carregando dados...",
    final_text: str = "✅ Dados carregados com sucesso!",
    delay: int = 3,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Demo: envia mensagem, espera N segundos e edita."""
    import asyncio

    ref_key = f"demo-{__import__('uuid').uuid7()}"

    record = await send_and_store(
        session,
        settings.telegram_channel_id,
        initial_text,
        reference_key=ref_key,
    )

    await asyncio.sleep(min(delay, 10))

    result = await edit_by_reference(session, ref_key, final_text)

    return {
        "reference_key": ref_key,
        "message_id": record.message_id,
        "initial_text": initial_text,
        "final_text": final_text,
        "delay": delay,
        "status": "done" if result else "error",
    }
