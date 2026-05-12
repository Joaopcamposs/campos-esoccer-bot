"""Testes scraper totalcorner — parsing HTML e cache."""

from unittest.mock import AsyncMock, patch

import pytest

from app.scrapers.totalcorner import (
    MatchResult,
    PlayerGoalStats,
    PlayerStats,
    _parse_goal_stats,
    _parse_player_stats,
    _parse_results,
    fetch_goal_stats,
    fetch_player_stats,
    fetch_results,
    invalidate_cache,
)

SAMPLE_HTML = """
<html><body>
<table class="stats_table">
  <tr><td></td><td>Player</td><td>MP</td><td>Win</td><td>Draw</td><td>Lose</td>
  <td>GF</td><td>GA</td><td>Avg. GF</td><td>Avg. GA</td><td>DA/G</td><td>Points</td></tr>
  <tr>
    <td>1</td>
    <td><a href="/esoccer-player/volvo/12995">volvo</a></td>
    <td>60</td><td>33</td><td>6</td><td>21</td>
    <td>200</td><td>158</td><td>3.3</td><td>2.6</td>
    <td>0</td><td>105</td>
  </tr>
  <tr>
    <td>2</td>
    <td><a href="/esoccer-player/Grellz/12995">Grellz</a></td>
    <td>45</td><td>25</td><td>5</td><td>15</td>
    <td>150</td><td>100</td><td>3.3</td><td>2.2</td>
    <td>0</td><td>80</td>
  </tr>
</table>
<table class="stats_table">
  <tr><td></td><td>Player</td><td>MP</td><td>Avg. GF</td><td>Avg. GA</td>
  <td>Over 1.5</td><td>Over 2.5</td><td>Over 3.5</td><td>Over 4.5</td>
  <td>Over 5.5</td><td>Over 6.5</td><td>Over 7.5</td><td>Over 8.5</td>
  <td>Over 9.5</td><td>Over 10.5</td></tr>
  <tr>
    <td>1</td><td>Wboy</td><td>53</td><td>3.5</td><td>3.2</td>
    <td>100%</td><td>100%</td><td>98%</td><td>85%</td><td>70%</td>
    <td>57%</td><td>36%</td><td>19%</td><td>8%</td><td>0%</td>
  </tr>
  <tr>
    <td>2</td><td>Cappo</td><td>40</td><td>3.4</td><td>4.0</td>
    <td>100%</td><td>100%</td><td>95%</td><td>93%</td><td>75%</td>
    <td>55%</td><td>38%</td><td>33%</td><td>20%</td><td>10%</td>
  </tr>
</table>
</body></html>
"""

RESULTS_HTML = """
<html><body>
<table class="table background_table">
  <tr><td colspan="15">May 2026</td></tr>
  <tr>
    <td>05/12 19:51</td><td>Full</td>
    <td>Germany (Simaponika)</td><td>4 - 3</td><td>Argentina (Kavviro)</td>
    <td></td><td>1 - 0</td><td>1 - 0</td><td></td><td></td>
    <td></td><td></td><td>-</td><td>4 - 3</td><td>C.O.L.</td>
  </tr>
  <tr>
    <td>05/12 19:51</td><td>Full</td>
    <td>England (Nightxx)</td><td>0 - 1</td><td>France (Grellz)</td>
    <td></td><td>1 - 3</td><td>1 - 3</td><td></td><td></td>
    <td></td><td></td><td>-</td><td>- 1</td><td>C.O.L.</td>
  </tr>
  <tr>
    <td>05/12 19:59</td><td>06 '</td>
    <td>Sporting (Kodak)</td><td>2 - 1</td><td>FC Porto (Inquisitor)</td>
    <td></td><td>0 - 1</td><td>0 - 1</td><td></td><td></td>
    <td></td><td></td><td>-</td><td>2 - 1</td><td>C.O.L.</td>
  </tr>
</table>
</body></html>
"""

NO_TABLE_HTML = "<html><body><p>Nothing here</p></body></html>"


def test_parse_player_stats():
    players = _parse_player_stats(SAMPLE_HTML)
    assert len(players) == 2
    assert players[0].player == "volvo"
    assert players[0].matches_played == 60
    assert players[0].wins == 33
    assert players[0].goals_for == 200
    assert players[0].avg_goals_for == 3.3
    assert players[0].points == 105


def test_parse_player_stats_no_table():
    assert _parse_player_stats(NO_TABLE_HTML) == []


def test_parse_goal_stats():
    stats = _parse_goal_stats(SAMPLE_HTML)
    assert len(stats) == 2
    assert stats[0].player == "Wboy"
    assert stats[0].matches_played == 53
    assert stats[0].avg_goals_for == 3.5
    assert stats[0].avg_goals_against == 3.2
    assert stats[0].over_pcts["3.5"] == 98.0
    assert stats[0].over_pcts["10.5"] == 0.0
    assert stats[1].player == "Cappo"
    assert stats[1].over_pcts["4.5"] == 93.0


def test_parse_goal_stats_no_second_table():
    html_one_table = """<html><body>
    <table class="stats_table"><tr><td>x</td></tr></table>
    </body></html>"""
    assert _parse_goal_stats(html_one_table) == []


def test_player_stats_to_dict():
    s = PlayerStats(
        player="volvo",
        matches_played=60,
        wins=33,
        draws=6,
        losses=21,
        goals_for=200,
        goals_against=158,
        avg_goals_for=3.3,
        avg_goals_against=2.6,
        points=105,
    )
    d = s.to_dict()
    assert d["player"] == "volvo"
    assert d["avg_goals_for"] == 3.3


def test_goal_stats_to_dict():
    s = PlayerGoalStats(
        player="Wboy",
        matches_played=53,
        avg_goals_for=3.5,
        avg_goals_against=3.2,
        over_pcts={"1.5": 100.0, "2.5": 100.0},
    )
    d = s.to_dict()
    assert d["player"] == "Wboy"
    assert d["over_pcts"]["1.5"] == 100.0


def test_parse_results():
    results = _parse_results(RESULTS_HTML)
    assert len(results) == 3
    assert results[0].home_team == "Germany"
    assert results[0].home_player == "Simaponika"
    assert results[0].away_player == "Kavviro"
    assert results[0].home_goals == 4
    assert results[0].away_goals == 3
    assert results[0].total_goals == 7
    assert results[0].status == "Full"
    assert results[0].kickoff_brt.hour == 15
    assert results[2].status == "06 '"


def test_parse_results_no_table():
    assert _parse_results(NO_TABLE_HTML) == []


def test_match_result_to_dict():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    r = MatchResult(
        kickoff_brt=datetime(2026, 5, 12, 16, 51, tzinfo=ZoneInfo("America/Sao_Paulo")),
        status="Full",
        home_team="Germany",
        home_player="Simaponika",
        away_team="Argentina",
        away_player="Kavviro",
        home_goals=4,
        away_goals=3,
    )
    d = r.to_dict()
    assert d["total_goals"] == 7
    assert d["home_player"] == "Simaponika"


class _FakeResponse:
    def __init__(self, html):
        self.text = html
        self.status_code = 200

    def raise_for_status(self):
        pass


@pytest.fixture(autouse=True)
def _clear_cache():
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.mark.asyncio
async def test_fetch_player_stats():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_FakeResponse(SAMPLE_HTML))

    with patch("app.scrapers.totalcorner.httpx.AsyncClient", return_value=mock_client):
        players = await fetch_player_stats()

    assert len(players) == 2
    assert players[0].player == "volvo"


@pytest.mark.asyncio
async def test_fetch_goal_stats():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_FakeResponse(SAMPLE_HTML))

    with patch("app.scrapers.totalcorner.httpx.AsyncClient", return_value=mock_client):
        stats = await fetch_goal_stats()

    assert len(stats) == 2
    assert stats[0].player == "Wboy"


@pytest.mark.asyncio
async def test_cache_reuses_html():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_FakeResponse(SAMPLE_HTML))

    with patch("app.scrapers.totalcorner.httpx.AsyncClient", return_value=mock_client):
        await fetch_player_stats()
        await fetch_goal_stats()

    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_cache_expires():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_FakeResponse(SAMPLE_HTML))

    with (
        patch("app.scrapers.totalcorner.httpx.AsyncClient", return_value=mock_client),
        patch("app.scrapers.totalcorner.time.monotonic", side_effect=[0, 300]),
    ):
        await fetch_player_stats()
        await fetch_player_stats()

    assert mock_client.get.call_count == 2


@pytest.mark.asyncio
async def test_fetch_results_finished_only():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_FakeResponse(RESULTS_HTML))

    with patch("app.scrapers.totalcorner.httpx.AsyncClient", return_value=mock_client):
        results = await fetch_results(finished_only=True)

    assert len(results) == 2
    assert all(r.status == "Full" for r in results)


@pytest.mark.asyncio
async def test_fetch_results_all():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_FakeResponse(RESULTS_HTML))

    with patch("app.scrapers.totalcorner.httpx.AsyncClient", return_value=mock_client):
        results = await fetch_results(finished_only=False)

    assert len(results) == 3
