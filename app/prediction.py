"""Motor de palpites — cruza dados locais e externos para gerar previsão de gols."""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.scrapers.aceodds import Match
from app.scrapers.totalcorner import (
    PlayerGoalStats,
    PlayerStats,
    fetch_goal_stats,
    fetch_player_stats,
)
from infra.models import PlayerLocalStats

logger = logging.getLogger(__name__)

MIN_LOCAL_MATCHES = 20


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


async def _get_local_stats(session: AsyncSession, player: str) -> PlayerLocalStats | None:
    stmt = select(PlayerLocalStats).where(PlayerLocalStats.player == player)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


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


async def generate_prediction(
    session: AsyncSession,
    match: Match,
) -> PredictionResult:
    """Gera palpite pra uma partida cruzando dados locais e externos."""
    home_local = await _get_local_stats(session, match.home_player)
    away_local = await _get_local_stats(session, match.away_player)

    use_local_home = home_local and home_local.matches_played >= MIN_LOCAL_MATCHES
    use_local_away = away_local and away_local.matches_played >= MIN_LOCAL_MATCHES

    ext_player_stats = await fetch_player_stats()
    ext_goal_stats = await fetch_goal_stats()

    if use_local_home:
        home_avg_gf = home_local.avg_goals_for
        home_avg_ga = home_local.avg_goals_against
        source_home = "local"
    else:
        ext = _find_external_stats(match.home_player, ext_player_stats)
        if ext:
            home_avg_gf = ext.avg_goals_for
            home_avg_ga = ext.avg_goals_against
            source_home = "external"
        else:
            home_avg_gf = 2.8
            home_avg_ga = 2.5
            source_home = "default"

    if use_local_away:
        away_avg_gf = away_local.avg_goals_for
        away_avg_ga = away_local.avg_goals_against
        source_away = "local"
    else:
        ext = _find_external_stats(match.away_player, ext_player_stats)
        if ext:
            away_avg_gf = ext.avg_goals_for
            away_avg_ga = ext.avg_goals_against
            source_away = "external"
        else:
            away_avg_gf = 2.8
            away_avg_ga = 2.5
            source_away = "default"

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
