"""Job principal — ciclo completo eSoccer Battle a cada 4 minutos."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from prediction import generate_prediction
from scheduler import register
from scrapers.aceodds import fetch_upcoming_matches
from scrapers.totalcorner import fetch_results
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from telegram import client

from infra.config import settings
from infra.database import async_session
from infra.models import PlayerLocalStats, Prediction

logger = logging.getLogger(__name__)

BRT = ZoneInfo("America/Sao_Paulo")


def _format_brt_time(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BRT)
    return dt.astimezone(BRT).strftime("%H:%M")


def _make_match_key(kickoff: datetime, home_player: str, away_player: str) -> str:
    """Chave única por bloco de 15min — tolerante a variação de timezone entre ciclos."""
    kickoff_brt = kickoff.astimezone(BRT)
    block = kickoff_brt.minute // 15
    return f"{kickoff_brt.strftime('%Y%m%d_%H')}_{block}_{home_player}_{away_player}"


def _format_prediction_message(pred) -> str:
    m = pred.match
    over_pct_text = f" ({pred.over_pct:.0f}%)" if pred.over_pct is not None else ""

    reasons = (
        f"👨🏻{m.home_player}: AVG [GF: {pred.home_avg_gf:.2f} | GA: {pred.home_avg_ga:.2f}]\n"
        f"🧔🏻{m.away_player}: AVG [GF: {pred.away_avg_gf:.2f} | GA: {pred.away_avg_ga:.2f}]\n"
        f"Frequência de gols acima de {pred.over_line}{over_pct_text}"
    )

    return (
        "E-soccer Battle 8 minutos - LIVE @1.5+\n\n"
        f"🎯 {m.home_player} ({m.home_team}) vs "
        f"{m.away_player} ({m.away_team})\n"
        f"⚽️ Gols esperado: {pred.expected_total_goals:.2f}\n"
        f"🥅 Over {pred.over_line} gols\n"
        f"🕒 {_format_brt_time(m.kickoff)}\n\n"
        f"📝Análise:\n{reasons}"
    )


async def send_predictions(window_minutes: int = 10) -> list[dict]:
    """
    Busca jogos próximos, gera palpites e envia no Telegram. Retorna palpites enviados.
    """
    matches = await fetch_upcoming_matches(window_minutes=window_minutes)
    if not matches:
        logger.info("Nenhum jogo nos próximos %d minutos", window_minutes)
        return []

    chat_id = settings.telegram_channel_id
    if not chat_id:
        logger.warning("TELEGRAM_CHANNEL_ID não configurado")
        return []

    sent: list[dict] = []

    async with async_session() as session:
        for match in matches:
            match_key = _make_match_key(match.kickoff, match.home_player, match.away_player)

            # Reserva o registro antes de enviar — impede envio duplicado mesmo com
            # concorrência
            prediction = Prediction(
                match_key=match_key,
                kickoff_brt=match.kickoff,
                home_team=match.home_team,
                home_player=match.home_player,
                away_team=match.away_team,
                away_player=match.away_player,
                expected_total_goals=0.0,
                over_line=0.0,
                status="reserving",
            )
            session.add(prediction)
            try:
                await session.flush()
            except IntegrityError:
                await session.rollback()
                logger.debug("Palpite já existe (UNIQUE): %s", match_key)
                continue

            pred = await generate_prediction(session, match)
            text = _format_prediction_message(pred)

            try:
                result = await client.send_message(chat_id, text)
                msg_id = result["result"]["message_id"]
            except Exception:
                logger.exception("Falha ao enviar palpite: %s", match_key)
                await session.rollback()
                continue

            prediction.expected_total_goals = pred.expected_total_goals
            prediction.over_line = pred.over_line
            prediction.message_id = msg_id
            prediction.status = "pending"
            await session.commit()
            logger.info("Palpite salvo: %s msg_id=%d", match_key, msg_id)

            sent.append(
                {
                    "match_key": match_key,
                    "home_player": match.home_player,
                    "away_player": match.away_player,
                    "expected_total_goals": pred.expected_total_goals,
                    "over_line": pred.over_line,
                    "message_id": msg_id,
                }
            )

    return sent


async def update_results() -> list[dict]:
    """
    Consulta resultados finalizados e atualiza palpites pendentes. Retorna atualizados.
    """
    results = await fetch_results(finished_only=True)
    if not results:
        return []

    updated: list[dict] = []

    async with async_session() as session:
        stmt = select(Prediction).where(Prediction.status == "pending")
        pending = (await session.execute(stmt)).scalars().all()
        if not pending:
            return []

        now_brt = datetime.now(BRT)
        used_results: set[int] = set()

        for pred in pending:
            kickoff = pred.kickoff_brt
            if kickoff and kickoff.tzinfo is None:
                kickoff = kickoff.replace(tzinfo=BRT)
            if kickoff and kickoff.astimezone(BRT) > now_brt:
                logger.debug("Prediction %s ainda não iniciou, ignorando", pred.match_key)
                continue

            pred_kickoff_brt = kickoff.astimezone(BRT) if kickoff else None

            matched = None
            best_diff = float("inf")
            for i, r in enumerate(results):
                if i in used_results:
                    continue
                if (
                    r.home_player.lower() != pred.home_player.lower()
                    or r.away_player.lower() != pred.away_player.lower()
                ):
                    continue
                if pred_kickoff_brt:
                    r_kickoff = r.kickoff_brt
                    if r_kickoff.tzinfo is None:
                        r_kickoff = r_kickoff.replace(tzinfo=BRT)
                    diff = abs((r_kickoff.astimezone(BRT) - pred_kickoff_brt).total_seconds())
                else:
                    diff = 0
                if diff < best_diff:
                    best_diff = diff
                    matched = (i, r)

            if not matched:
                continue

            result_idx, matched = matched
            used_results.add(result_idx)

            total = matched.total_goals
            success = total > pred.over_line
            icon = "✅" if success else "❌"

            try:
                await client.api_call(
                    "editMessageText",
                    chat_id=settings.telegram_channel_id,
                    message_id=pred.message_id,
                    parse_mode="HTML",
                    text=(
                        f"E-soccer Battle 8 minutos - LIVE @1.5+\n\n"
                        f"🎯 {pred.home_player} ({pred.home_team}) vs "
                        f"{pred.away_player} ({pred.away_team})\n"
                        f"⚽️ Gols esperado: {pred.expected_total_goals:.2f}\n"
                        f"🥅 Over {pred.over_line} gols\n"
                        f"🕒 {_format_brt_time(pred.kickoff_brt)}\n\n"
                        f"Resultado: {matched.home_goals} - {matched.away_goals} "
                        f"(total: {total})\n\n"
                        f"{icon}"
                    ),
                )
            except Exception:
                logger.exception(
                    "Falha ao editar mensagem pred=%s — mantendo pending", pred.id
                )
                continue

            pred.home_goals = matched.home_goals
            pred.away_goals = matched.away_goals
            pred.success = success
            pred.status = "done"

            await _update_local_stats(session, matched)
            logger.info(
                "Resultado atualizado: %s %d-%d %s",
                pred.match_key,
                matched.home_goals,
                matched.away_goals,
                icon,
            )

            updated.append(
                {
                    "match_key": pred.match_key,
                    "home_goals": matched.home_goals,
                    "away_goals": matched.away_goals,
                    "total_goals": total,
                    "over_line": pred.over_line,
                    "success": pred.success,
                }
            )

        await session.commit()

    return updated


async def _update_local_stats(session, result) -> None:
    """Atualiza estatísticas locais dos dois jogadores após resultado."""
    for player, gf, ga in [
        (result.home_player, result.home_goals, result.away_goals),
        (result.away_player, result.away_goals, result.home_goals),
    ]:
        stmt = select(PlayerLocalStats).where(PlayerLocalStats.player == player)
        stats = (await session.execute(stmt)).scalar_one_or_none()

        if not stats:
            stats = PlayerLocalStats(
                player=player,
                matches_played=0,
                goals_for=0,
                goals_against=0,
                wins=0,
                draws=0,
                losses=0,
            )
            session.add(stats)

        stats.matches_played += 1
        stats.goals_for += gf
        stats.goals_against += ga

        if gf > ga:
            stats.wins += 1
        elif gf == ga:
            stats.draws += 1
        else:
            stats.losses += 1


async def simulate_e2e(limit: int = 5) -> list[dict]:
    """Teste e2e: pega resultados reais, gera palpites, envia e atualiza com resultado."""
    results = await fetch_results(finished_only=True)
    if not results:
        return []

    from scrapers.aceodds import Match

    chat_id = settings.telegram_channel_id
    if not chat_id:
        return []

    results = results[:limit]
    output: list[dict] = []

    async with async_session() as session:
        for r in results:
            match = Match(
                kickoff=r.kickoff_brt,
                home_team=r.home_team,
                home_player=r.home_player,
                away_team=r.away_team,
                away_player=r.away_player,
            )

            match_key = _make_match_key(r.kickoff_brt, r.home_player, r.away_player)

            existing = await session.execute(
                select(Prediction).where(Prediction.match_key == match_key)
            )
            if existing.scalar_one_or_none():
                continue

            pred = await generate_prediction(session, match)
            text = _format_prediction_message(pred)

            try:
                msg_result = await client.send_message(chat_id, text)
                msg_id = msg_result["result"]["message_id"]
            except Exception:
                logger.exception("Simulate e2e: falha envio %s", match_key)
                continue

            prediction = Prediction(
                match_key=match_key,
                kickoff_brt=r.kickoff_brt,
                home_team=r.home_team,
                home_player=r.home_player,
                away_team=r.away_team,
                away_player=r.away_player,
                expected_total_goals=pred.expected_total_goals,
                over_line=pred.over_line,
                message_id=msg_id,
                status="pending",
            )
            session.add(prediction)
            await session.commit()

            total = r.total_goals
            prediction.home_goals = r.home_goals
            prediction.away_goals = r.away_goals
            prediction.success = total > pred.over_line
            prediction.status = "done"

            icon = "✅" if prediction.success else "❌"

            try:
                await client.api_call(
                    "editMessageText",
                    chat_id=chat_id,
                    message_id=msg_id,
                    parse_mode="HTML",
                    text=(
                        f"E-soccer Battle 8 minutos - LIVE @1.5+\n\n"
                        f"🎯 {r.home_player} ({r.home_team}) vs "
                        f"{r.away_player} ({r.away_team})\n"
                        f"⚽️ Gols esperado: {pred.expected_total_goals:.2f}\n"
                        f"🥅 Over {pred.over_line} gols\n"
                        f"🕒 {_format_brt_time(r.kickoff_brt)}\n\n"
                        f"Resultado: {r.home_goals} - {r.away_goals} "
                        f"(total: {total})\n\n"
                        f"{icon}"
                    ),
                )
            except Exception:
                logger.exception("Simulate e2e: falha edição %s", match_key)

            await _update_local_stats(session, r)
            await session.commit()

            output.append(
                {
                    "match_key": match_key,
                    "home_player": r.home_player,
                    "away_player": r.away_player,
                    "expected_total_goals": pred.expected_total_goals,
                    "over_line": pred.over_line,
                    "result": f"{r.home_goals}-{r.away_goals}",
                    "total_goals": total,
                    "success": prediction.success,
                }
            )

            logger.info(
                "Simulate e2e: %s → %d-%d %s",
                match_key,
                r.home_goals,
                r.away_goals,
                icon,
            )

    return output


@register("esoccer-battle", interval_seconds=240)
async def esoccer_cycle():
    """Ciclo completo: gerar palpites + atualizar resultados."""
    logger.info("Iniciando ciclo eSoccer Battle")
    await send_predictions()
    await update_results()
    logger.info("Ciclo eSoccer Battle concluído")
