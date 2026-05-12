"""Testes job eSoccer — formatação e match_key."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.jobs.esoccer import _format_brt_time, _make_match_key

BRT = ZoneInfo("America/Sao_Paulo")


def test_format_brt_time():
    dt = datetime(2026, 5, 12, 14, 30, tzinfo=BRT)
    assert _format_brt_time(dt) == "14:30"


def test_make_match_key():
    dt = datetime(2026, 5, 12, 14, 0, tzinfo=BRT)
    key = _make_match_key(dt, "Grellz", "Simaponika")
    assert key == "20260512_1400_Grellz_Simaponika"


def test_make_match_key_unique():
    dt1 = datetime(2026, 5, 12, 14, 0, tzinfo=BRT)
    dt2 = datetime(2026, 5, 12, 14, 12, tzinfo=BRT)
    k1 = _make_match_key(dt1, "Grellz", "Simaponika")
    k2 = _make_match_key(dt2, "Grellz", "Simaponika")
    assert k1 != k2
