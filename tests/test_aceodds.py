"""Testes scraper aceodds — parsing HTML e filtro por janela de tempo."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.scrapers.aceodds import (
    BRT,
    Match,
    _parse_date_header,
    _parse_match_text,
    fetch_upcoming_matches,
)

SAMPLE_HTML = """
<html><body>
<table class="table mt-n3 table-sm-sm">
  <tr>
    <td colspan="2" class="px-0 pt-4 pb-2">
      <h2 class="m-0 fs-5 fw-bold">Ter, 12 Maio 2026 - Partidas de Hoje</h2>
    </td>
  </tr>
  <tr><th>Hora de início</th><th>Evento</th></tr>
  <tr>
    <td>14:00</td>
    <td><a href="/link" title="test">France (Grellz) x Germany (Simaponika)</a></td>
  </tr>
  <tr>
    <td>14:00</td>
    <td><a href="/link" title="test">Brazil (KaiZer) x Spain (M4theus)</a></td>
  </tr>
  <tr>
    <td>14:12</td>
    <td><a href="/link" title="test">Italy (Luca99) x England (JohnD)</a></td>
  </tr>
  <tr>
    <td>18:00</td>
    <td><a href="/link" title="test">Argentina (PepeG) x Portugal (CR7fan)</a></td>
  </tr>
</table>
</body></html>
"""


def test_parse_match_text():
    result = _parse_match_text("France (Grellz) x Germany (Simaponika)")
    assert result == ("France", "Grellz", "Germany", "Simaponika")


def test_parse_match_text_invalid():
    assert _parse_match_text("invalid text") is None


def test_parse_date_header():
    fallback = datetime(2026, 1, 1, tzinfo=BRT)
    dt = _parse_date_header("Ter, 12 Maio 2026 - Partidas de Hoje", fallback)
    assert dt.day == 12
    assert dt.month == 5
    assert dt.year == 2026


def test_parse_date_header_fallback():
    fallback = datetime(2026, 6, 15, tzinfo=BRT)
    dt = _parse_date_header("texto invalido", fallback)
    assert dt == fallback


class _FakeResponse:
    status_code = 200
    text = SAMPLE_HTML

    def raise_for_status(self):
        pass


@pytest.mark.asyncio
async def test_fetch_upcoming_matches_filters_by_window():
    fixed_now = datetime(2026, 5, 12, 13, 58, 0, tzinfo=BRT)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_FakeResponse())

    with (
        patch("app.scrapers.aceodds.httpx.AsyncClient", return_value=mock_client),
        patch("app.scrapers.aceodds.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        matches = await fetch_upcoming_matches(window_minutes=5)

    assert len(matches) == 2
    assert matches[0].home_player == "Grellz"
    assert matches[1].home_player == "KaiZer"
    assert all(m.kickoff.hour == 14 and m.kickoff.minute == 0 for m in matches)


@pytest.mark.asyncio
async def test_fetch_no_matches_outside_window():
    fixed_now = datetime(2026, 5, 12, 10, 0, 0, tzinfo=BRT)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_FakeResponse())

    with (
        patch("app.scrapers.aceodds.httpx.AsyncClient", return_value=mock_client),
        patch("app.scrapers.aceodds.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        matches = await fetch_upcoming_matches(window_minutes=5)

    assert len(matches) == 0


def test_match_to_dict():
    m = Match(
        kickoff=datetime(2026, 5, 12, 14, 0, tzinfo=BRT),
        home_team="France",
        home_player="Grellz",
        away_team="Germany",
        away_player="Simaponika",
    )
    d = m.to_dict()
    assert d["home_player"] == "Grellz"
    assert "kickoff" in d
