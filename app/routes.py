"""Rotas API — endpoints de negócio."""

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException
from jobs.esoccer import send_predictions, simulate_e2e, update_results
from scrapers.aceodds import HEADERS as ACEODDS_HEADERS
from scrapers.aceodds import URL as ACEODDS_URL
from scrapers.aceodds import fetch_upcoming_matches
from scrapers.totalcorner import fetch_goal_stats, fetch_player_stats, fetch_results
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


@router.get("/results")
async def api_results(
    player: str | None = None,
    finished_only: bool = True,
) -> dict[str, Any]:
    """Resultados recentes eSoccer Battle (totalcorner)."""
    results = await fetch_results(finished_only=finished_only)
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
async def api_send_predictions(window: int = 10) -> dict[str, Any]:
    """Força envio de palpites dos próximos jogos."""
    sent = await send_predictions(window_minutes=window)
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


@router.get("/debug/aceodds-raw")
async def debug_aceodds_raw() -> dict[str, Any]:
    """Retorna horários brutos do aceodds sem conversão — pra debug de timezone."""
    async with httpx.AsyncClient(timeout=15.0, headers=ACEODDS_HEADERS) as client:
        resp = await client.get(ACEODDS_URL)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.select_one("table.table")
    if not table:
        return {"error": "tabela não encontrada"}

    rows = []
    current_header = ""
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) == 1:
            h2 = cells[0].find("h2")
            if h2:
                current_header = h2.get_text(strip=True)
            continue
        if len(cells) < 2:
            continue
        time_text = cells[0].get_text(strip=True)
        if not re.match(r"^\d{1,2}:\d{2}$", time_text):
            continue
        link = cells[1].find("a")
        match_text = link.get_text(strip=True) if link else cells[1].get_text(strip=True)
        rows.append(
            {
                "date_header": current_header,
                "time_raw": time_text,
                "match": match_text,
            }
        )

    now_utc = datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S")
    now_brt = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")
    now_est = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "server_now_utc": now_utc,
        "server_now_brt": now_brt,
        "server_now_est": now_est,
        "total_rows": len(rows),
        "rows": rows[:20],
    }


@router.get("/debug/totalcorner-raw")
async def debug_totalcorner_raw() -> dict[str, Any]:
    """Retorna horários brutos do totalcorner sem conversão — pra debug de timezone."""
    from scrapers.totalcorner import BASE_URL
    from scrapers.totalcorner import HEADERS as TC_HEADERS

    async with httpx.AsyncClient(timeout=20.0, headers=TC_HEADERS) as client:
        resp = await client.get(BASE_URL)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    tables = soup.find_all("table", class_="background_table")
    if not tables:
        return {"error": "tabela de resultados não encontrada"}

    table = tables[-1]
    rows = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 5:
            continue
        date_text = cells[0].get_text(strip=True)
        if not re.match(r"^\d{2}/\d{2}\s+\d{2}:\d{2}$", date_text):
            continue
        status = cells[1].get_text(strip=True)
        home = cells[2].get_text(strip=True)
        score = cells[3].get_text(strip=True)
        away = cells[4].get_text(strip=True)
        rows.append(
            {
                "datetime_raw": date_text,
                "status": status,
                "home": home,
                "score": score,
                "away": away,
            }
        )

    now_utc = datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S")
    now_brt = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "server_now_utc": now_utc,
        "server_now_brt": now_brt,
        "total_rows": len(rows),
        "rows": rows[:20],
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
