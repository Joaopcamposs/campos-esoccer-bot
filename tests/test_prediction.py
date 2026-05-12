"""Testes motor de palpites."""

from datetime import datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from prediction import (
    PredictionResult,
    _pick_over_line,
    generate_prediction,
)
from scrapers.aceodds import Match
from scrapers.totalcorner import PlayerGoalStats, PlayerStats

BRT = ZoneInfo("America/Sao_Paulo")


def _make_match() -> Match:
    return Match(
        kickoff=datetime(2026, 5, 12, 14, 0, tzinfo=BRT),
        home_team="France",
        home_player="Grellz",
        away_team="Germany",
        away_player="Simaponika",
    )


def test_pick_over_line():
    assert _pick_over_line(5.8) == 4.5
    assert _pick_over_line(6.5) == 5.5
    assert _pick_over_line(3.2) == 2.5
    assert _pick_over_line(1.0) == 1.5


@pytest.mark.asyncio
async def test_generate_prediction_external():
    match = _make_match()

    ext_stats = [
        PlayerStats("Grellz", 50, 30, 5, 15, 180, 120, 3.6, 2.4, 95),
        PlayerStats("Simaponika", 50, 25, 10, 15, 150, 130, 3.0, 2.6, 85),
    ]
    goal_stats = [
        PlayerGoalStats("Grellz", 50, 3.6, 2.4, {"4.5": 80.0, "5.5": 60.0}),
        PlayerGoalStats("Simaponika", 50, 3.0, 2.6, {"4.5": 70.0, "5.5": 50.0}),
    ]

    from unittest.mock import MagicMock

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with (
        patch("prediction.fetch_player_stats", return_value=ext_stats),
        patch("prediction.fetch_goal_stats", return_value=goal_stats),
    ):
        pred = await generate_prediction(mock_session, match)

    assert isinstance(pred, PredictionResult)
    assert pred.home_avg_gf == 3.6
    assert pred.away_avg_gf == 3.0
    assert pred.expected_total_goals > 0
    assert pred.over_line >= 1.5
    assert "external" in pred.source


@pytest.mark.asyncio
async def test_generate_prediction_default_fallback():
    match = _make_match()

    from unittest.mock import MagicMock

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with (
        patch("prediction.fetch_player_stats", return_value=[]),
        patch("prediction.fetch_goal_stats", return_value=[]),
    ):
        pred = await generate_prediction(mock_session, match)

    assert pred.home_avg_gf == 2.8
    assert pred.away_avg_gf == 2.8
    assert "default" in pred.source
