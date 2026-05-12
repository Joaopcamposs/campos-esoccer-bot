"""Testes scraper totalcorner — parsing HTML."""

from unittest.mock import AsyncMock, patch

import pytest

from app.scrapers.totalcorner import (
    PlayerStats,
    _parse_table_page,
    fetch_player_stats,
)

SAMPLE_HTML = """
<html><body>
<table class="stats_table">
<tbody>
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
</tbody>
</table>
</body></html>
"""

NO_TABLE_HTML = "<html><body><p>Nothing here</p></body></html>"


def test_parse_table_page():
    players = _parse_table_page(SAMPLE_HTML)
    assert len(players) == 2
    assert players[0].player == "volvo"
    assert players[0].matches_played == 60
    assert players[0].wins == 33
    assert players[0].goals_for == 200
    assert players[0].avg_goals_for == 3.3
    assert players[0].points == 105
    assert players[1].player == "Grellz"


def test_parse_table_page_no_table():
    assert _parse_table_page(NO_TABLE_HTML) == []


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


class _FakeResponse:
    def __init__(self, html):
        self.text = html
        self.status_code = 200

    def raise_for_status(self):
        pass


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
