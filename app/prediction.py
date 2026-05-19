"""Motor de palpites — cruza dados locais e externos para gerar previsão de gols."""

import logging
from dataclasses import dataclass

from scrapers.tipmanager import Match
from scrapers.totalcorner import (
    PlayerGoalStats,
    PlayerStats,
    fetch_goal_stats,
    fetch_player_stats,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.models import PlayerMatch

logger = logging.getLogger(__name__)

LOCAL_THRESHOLDS = [20, 10]


@dataclass
class PredictionResult:
    match: Match
    expected_total_goals: float
    over_line: float
    home_avg_gf: float
    home_avg_ga: float
    away_avg_gf: float
    away_avg_ga: float
    over_pct: float | None
    source: str


async def _get_local_avg(
    session: AsyncSession, player: str, last_n: int = 20
) -> tuple[float, float, int] | None:
    """Retorna (avg_gf, avg_ga, count) das últimas N partidas do jogador."""
    subq = (
        select(PlayerMatch.goals_for, PlayerMatch.goals_against)
        .where(PlayerMatch.player == player)
        .order_by(PlayerMatch.kickoff.desc())
        .limit(last_n)
        .subquery()
    )
    stmt = select(
        func.avg(subq.c.goals_for),
        func.avg(subq.c.goals_against),
        func.count(),
    )
    row = (await session.execute(stmt)).one()
    if row[2] == 0:
        return None
    return (float(row[0]), float(row[1]), row[2])


def _find_external_stats(
    player: str,
    player_stats: list[PlayerStats],
) -> PlayerStats | None:
    p = player.lower()
    for s in player_stats:
        if s.player.lower() == p:
            return s
    return None


def _find_goal_stats(
    player: str,
    goal_stats: list[PlayerGoalStats],
) -> PlayerGoalStats | None:
    p = player.lower()
    for s in goal_stats:
        if s.player.lower() == p:
            return s
    return None


def _pick_over_line(expected: float) -> float:
    """Escolhe linha over 1 gol abaixo do esperado, arredondada em .5, mínimo 1.5."""
    line = int(expected - 1) + 0.5
    return max(1.5, line)


def _get_over_pct(
    home_goal_stats: PlayerGoalStats | None,
    away_goal_stats: PlayerGoalStats | None,
    line: float,
) -> float | None:
    key = str(line)
    pcts = []
    if home_goal_stats and key in home_goal_stats.over_pcts:
        pcts.append(home_goal_stats.over_pcts[key])
    if away_goal_stats and key in away_goal_stats.over_pcts:
        pcts.append(away_goal_stats.over_pcts[key])
    if not pcts:
        return None
    return sum(pcts) / len(pcts)


async def _resolve_player_stats(
    session: AsyncSession, player: str, ext_stats: list[PlayerStats]
) -> tuple[float, float, str] | None:
    """Tenta local (20 → 10) depois externo. None se sem dados."""
    for n in LOCAL_THRESHOLDS:
        local = await _get_local_avg(session, player, last_n=n)
        if local and local[2] >= n:
            return local[0], local[1], f"local({local[2]})"

    ext = _find_external_stats(player, ext_stats)
    if ext:
        return ext.avg_goals_for, ext.avg_goals_against, "external"

    logger.warning("Sem dados para %s — sem local nem externo", player)
    return None


async def generate_prediction(
    session: AsyncSession,
    match: Match,
) -> PredictionResult | None:
    """Gera palpite pra uma partida cruzando dados locais e externos. None se sem dados."""
    ext_player_stats = await fetch_player_stats()
    ext_goal_stats = await fetch_goal_stats()

    home_result = await _resolve_player_stats(
        session, match.home_player, ext_player_stats
    )
    if home_result is None:
        return None
    home_avg_gf, home_avg_ga, source_home = home_result

    away_result = await _resolve_player_stats(
        session, match.away_player, ext_player_stats
    )
    if away_result is None:
        return None
    away_avg_gf, away_avg_ga, source_away = away_result

    home_expected = (home_avg_gf + away_avg_ga) / 2
    away_expected = (away_avg_gf + home_avg_ga) / 2
    expected_total = home_expected + away_expected

    over_line = _pick_over_line(expected_total)

    home_gs = _find_goal_stats(match.home_player, ext_goal_stats)
    away_gs = _find_goal_stats(match.away_player, ext_goal_stats)
    over_pct = _get_over_pct(home_gs, away_gs, over_line)

    source = f"home={source_home},away={source_away}"

    logger.info(
        "Palpite: %s vs %s → %.1f gols, Over %.1f (%s)",
        match.home_player,
        match.away_player,
        expected_total,
        over_line,
        source,
    )

    return PredictionResult(
        match=match,
        expected_total_goals=expected_total,
        over_line=over_line,
        home_avg_gf=home_avg_gf,
        home_avg_ga=home_avg_ga,
        away_avg_gf=away_avg_gf,
        away_avg_ga=away_avg_ga,
        over_pct=over_pct,
        source=source,
    )
