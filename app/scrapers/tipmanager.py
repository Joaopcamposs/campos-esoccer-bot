"""Scraper tipmanager — resultados e próximos jogos eSoccer Battle 8min."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

URL = "https://tipmanager.net/pt/sports/e-soccer/leagues/1/battle"

BRT = ZoneInfo("America/Sao_Paulo")
UTC = ZoneInfo("UTC")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
}

_DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4}),\s*(\d{2}):(\d{2})$")
_ARIA_RE = re.compile(r"^(.+?) - (.+?) - Clique")


@dataclass
class Match:
    kickoff: datetime
    home_team: str
    home_player: str
    away_team: str
    away_player: str

    def to_dict(self) -> dict:
        return {
            "kickoff": self.kickoff.isoformat(),
            "home_team": self.home_team,
            "home_player": self.home_player,
            "away_team": self.away_team,
            "away_player": self.away_player,
        }


@dataclass
class MatchResult:
    kickoff_brt: datetime
    home_team: str
    home_player: str
    away_team: str
    away_player: str
    home_goals: int
    away_goals: int

    @property
    def total_goals(self) -> int:
        return self.home_goals + self.away_goals

    def to_dict(self) -> dict:
        return {
            "kickoff_brt": self.kickoff_brt.isoformat(),
            "home_team": self.home_team,
            "home_player": self.home_player,
            "away_team": self.away_team,
            "away_player": self.away_player,
            "home_goals": self.home_goals,
            "away_goals": self.away_goals,
            "total_goals": self.total_goals,
        }


def _parse_date(text: str) -> datetime | None:
    m = _DATE_RE.match(text.strip())
    if not m:
        return None
    day, month, year, hour, minute = (int(g) for g in m.groups())
    try:
        dt_utc = datetime(year, month, day, hour, minute, tzinfo=UTC)
        return dt_utc.astimezone(BRT)
    except ValueError:
        return None


def _parse_player_team(aria_label: str) -> tuple[str, str] | None:
    m = _ARIA_RE.match(aria_label)
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip()


def _parse_tables(html: str) -> tuple[list[Match], list[MatchResult]]:
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    if len(tables) < 2:
        logger.warning("Tipmanager: esperava 2 tabelas, encontrou %d", len(tables))
        return [], []

    upcoming = _parse_upcoming(tables[0])
    results = _parse_results(tables[1])
    return upcoming, results


def _parse_upcoming(table) -> list[Match]:
    matches = []
    for row in table.find_all("tr"):
        date_span = row.find("span", string=_DATE_RE)
        if not date_span:
            continue
        kickoff = _parse_date(date_span.get_text(strip=True))
        if not kickoff:
            continue

        links = row.find_all("a", attrs={"aria-label": _ARIA_RE})
        if len(links) < 2:
            continue

        home = _parse_player_team(links[0]["aria-label"])
        away = _parse_player_team(links[1]["aria-label"])
        if not home or not away:
            continue

        matches.append(
            Match(
                kickoff=kickoff,
                home_player=home[0],
                home_team=home[1],
                away_player=away[0],
                away_team=away[1],
            )
        )
    logger.info("Tipmanager upcoming: %d jogos", len(matches))
    return matches


def _parse_results(table) -> list[MatchResult]:
    results = []
    for row in table.find_all("tr"):
        date_span = row.find("span", string=_DATE_RE)
        if not date_span:
            continue
        kickoff = _parse_date(date_span.get_text(strip=True))
        if not kickoff:
            continue

        links = row.find_all("a", attrs={"aria-label": _ARIA_RE})
        if len(links) < 2:
            continue

        home = _parse_player_team(links[0]["aria-label"])
        away = _parse_player_team(links[1]["aria-label"])
        if not home or not away:
            continue

        score_div = row.find("div", class_=lambda c: c and "bg-accent" in c)
        if not score_div:
            continue
        score_spans = score_div.find_all("span")
        score_texts = [
            s.get_text(strip=True) for s in score_spans if s.get_text(strip=True).isdigit()
        ]
        if len(score_texts) < 2:
            continue

        try:
            home_goals = int(score_texts[0])
            away_goals = int(score_texts[1])
        except ValueError:
            continue

        results.append(
            MatchResult(
                kickoff_brt=kickoff,
                home_player=home[0],
                home_team=home[1],
                home_goals=home_goals,
                away_player=away[0],
                away_team=away[1],
                away_goals=away_goals,
            )
        )
    logger.info("Tipmanager results: %d jogos", len(results))
    return results


async def _fetch_html() -> str:
    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
        resp = await client.get(URL)
        resp.raise_for_status()
    return resp.text


async def fetch_upcoming_matches(window_minutes: int = 5) -> list[Match]:
    """Busca jogos que começam nos próximos `window_minutes` minutos (BRT)."""
    html = await _fetch_html()
    upcoming, _ = _parse_tables(html)

    now_brt = datetime.now(BRT)
    cutoff = now_brt + timedelta(minutes=window_minutes)

    filtered = [
        m for m in upcoming
        if now_brt <= m.kickoff <= cutoff
    ]
    logger.info(
        "Tipmanager: %d jogos nos próximos %d min (de %d total upcoming)",
        len(filtered),
        window_minutes,
        len(upcoming),
    )
    return filtered


async def fetch_results(finished_only: bool = True) -> list[MatchResult]:
    """Resultados recentes. finished_only mantido por compatibilidade (sempre retorna finalizados)."""
    html = await _fetch_html()
    _, results = _parse_tables(html)
    logger.info("Tipmanager results: %d jogos finalizados", len(results))
    return results


async def fetch_all() -> tuple[list[Match], list[MatchResult]]:
    """Busca upcoming e results em uma única requisição."""
    html = await _fetch_html()
    return _parse_tables(html)
