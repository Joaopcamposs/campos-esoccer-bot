"""Rotas API — endpoints de negócio."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from jobs.esoccer import send_predictions, simulate_e2e, update_results
from scrapers.tipmanager import fetch_results, fetch_upcoming_matches
from scrapers.totalcorner import fetch_goal_stats, fetch_player_stats
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.service import edit_by_reference, list_pending, send_and_store

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
async def api_upcoming() -> dict[str, Any]:
    """Próximos jogos eSoccer Battle (tipmanager)."""
    matches = await fetch_upcoming_matches()
    return {
        "count": len(matches),
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


@router.get("/results")
async def api_results(
    player: str | None = None,
) -> dict[str, Any]:
    """Resultados recentes eSoccer Battle (tipmanager)."""
    results = await fetch_results()
    if player:
        p = player.lower()
        results = [
            r for r in results if p in r.home_player.lower() or p in r.away_player.lower()
        ]
    return {
        "count": len(results),
        "results": [r.to_dict() for r in results],
    }


@router.post("/predictions/send")
async def api_send_predictions() -> dict[str, Any]:
    """Força envio de palpites dos próximos jogos."""
    sent = await send_predictions()
    return {
        "sent_count": len(sent),
        "predictions": sent,
    }


@router.post("/predictions/update")
async def api_update_results() -> dict[str, Any]:
    """Força atualização de resultados dos palpites pendentes."""
    updated = await update_results()
    return {
        "updated_count": len(updated),
        "results": updated,
    }


@router.post("/predictions/simulate")
async def api_simulate_e2e(limit: int = 5) -> dict[str, Any]:
    """Teste e2e: pega resultados reais, gera palpites, envia e atualiza."""
    results = await simulate_e2e(limit=limit)
    return {
        "count": len(results),
        "results": results,
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


@router.get("/debug/tipmanager-raw")
async def debug_tipmanager_raw() -> dict[str, Any]:
    """Retorna dados brutos do tipmanager — pra debug."""
    from scrapers.tipmanager import fetch_all

    upcoming, results = await fetch_all()
    now_brt = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "server_now_brt": now_brt,
        "upcoming_count": len(upcoming),
        "results_count": len(results),
        "upcoming": [m.to_dict() for m in upcoming[:20]],
        "results": [r.to_dict() for r in results[:20]],
    }


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
