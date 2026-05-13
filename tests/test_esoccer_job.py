"""Testes job eSoccer — formatação e match_key."""

from datetime import datetime
from zoneinfo import ZoneInfo

from jobs.esoccer import _format_brt_time, _make_match_key

BRT = ZoneInfo("America/Sao_Paulo")


def test_format_brt_time():
    dt = datetime(2026, 5, 12, 14, 30, tzinfo=BRT)
    assert _format_brt_time(dt) == "14:30"


def test_make_match_key():
    dt = datetime(2026, 5, 12, 14, 0, tzinfo=BRT)
    key = _make_match_key(dt, "Grellz", "Simaponika")
    # formato: YYYYMMDD_HH_bloco15min_home_away  (bloco = minuto // 15)
    assert key == "20260512_14_0_Grellz_Simaponika"


def test_make_match_key_same_block():
    """Minutos no mesmo bloco de 15min geram a mesma key — deduplicação tolerante."""
    dt1 = datetime(2026, 5, 12, 14, 0, tzinfo=BRT)
    dt2 = datetime(2026, 5, 12, 14, 8, tzinfo=BRT)
    assert _make_match_key(dt1, "Grellz", "Simaponika") == _make_match_key(
        dt2, "Grellz", "Simaponika"
    )


def test_make_match_key_different_block():
    """Minutos em blocos distintos geram keys diferentes."""
    dt1 = datetime(2026, 5, 12, 14, 0, tzinfo=BRT)
    dt2 = datetime(2026, 5, 12, 14, 16, tzinfo=BRT)
    assert _make_match_key(dt1, "Grellz", "Simaponika") != _make_match_key(
        dt2, "Grellz", "Simaponika"
    )
