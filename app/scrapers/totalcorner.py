"""Scraper totalcorner — stats e over/under de jogadores eSoccer Battle 8min."""

import logging
import time
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.totalcorner.com/league/view/12995/end/Esoccer-Battle-8-mins-play"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

CACHE_TTL = 240

_cache_html: str | None = None
_cache_ts: float = 0.0


@dataclass
class PlayerStats:
    player: str
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    avg_goals_for: float
    avg_goals_against: float
    points: int

    def to_dict(self) -> dict:
        return {
            "player": self.player,
            "matches_played": self.matches_played,
            "wins": self.wins,
            "draws": self.draws,
            "losses": self.losses,
            "goals_for": self.goals_for,
            "goals_against": self.goals_against,
            "avg_goals_for": self.avg_goals_for,
            "avg_goals_against": self.avg_goals_against,
            "points": self.points,
        }


OVER_THRESHOLDS = [1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5]


@dataclass
class PlayerGoalStats:
    player: str
    matches_played: int
    avg_goals_for: float
    avg_goals_against: float
    over_pcts: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "player": self.player,
            "matches_played": self.matches_played,
            "avg_goals_for": self.avg_goals_for,
            "avg_goals_against": self.avg_goals_against,
            "over_pcts": self.over_pcts,
        }


async def _fetch_html() -> str:
    global _cache_html, _cache_ts

    now = time.monotonic()
    if _cache_html and (now - _cache_ts) < CACHE_TTL:
        logger.debug(
            "Totalcorner: usando cache (%.0fs restante)", CACHE_TTL - (now - _cache_ts)
        )
        return _cache_html

    logger.info("Totalcorner: buscando página...")
    async with httpx.AsyncClient(timeout=20.0, headers=HEADERS) as client:
        resp = await client.get(BASE_URL)
        resp.raise_for_status()

    _cache_html = resp.text
    _cache_ts = now
    return _cache_html


def _parse_player_stats(html: str) -> list[PlayerStats]:
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table", class_="stats_table")
    if not tables:
        return []

    players: list[PlayerStats] = []
    for row in tables[0].find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 12:
            continue
        try:
            player_link = cells[1].find("a")
            name = (
                player_link.get_text(strip=True)
                if player_link
                else cells[1].get_text(strip=True)
            )
            players.append(
                PlayerStats(
                    player=name,
                    matches_played=int(cells[2].get_text(strip=True)),
                    wins=int(cells[3].get_text(strip=True)),
                    draws=int(cells[4].get_text(strip=True)),
                    losses=int(cells[5].get_text(strip=True)),
                    goals_for=int(cells[6].get_text(strip=True)),
                    goals_against=int(cells[7].get_text(strip=True)),
                    avg_goals_for=float(cells[8].get_text(strip=True)),
                    avg_goals_against=float(cells[9].get_text(strip=True)),
                    points=int(cells[11].get_text(strip=True)),
                )
            )
        except ValueError, IndexError:
            continue

    return players


def _parse_pct(text: str) -> float:
    return float(text.replace("%", ""))


def _parse_goal_stats(html: str) -> list[PlayerGoalStats]:
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table", class_="stats_table")
    if len(tables) < 2:
        return []

    players: list[PlayerGoalStats] = []
    for row in tables[1].find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 15:
            continue
        try:
            name = cells[1].get_text(strip=True)
            if not name or name == "Player":
                continue

            over_pcts = {}
            for i, threshold in enumerate(OVER_THRESHOLDS):
                over_pcts[str(threshold)] = _parse_pct(cells[5 + i].get_text(strip=True))

            players.append(
                PlayerGoalStats(
                    player=name,
                    matches_played=int(cells[2].get_text(strip=True)),
                    avg_goals_for=float(cells[3].get_text(strip=True)),
                    avg_goals_against=float(cells[4].get_text(strip=True)),
                    over_pcts=over_pcts,
                )
            )
        except ValueError, IndexError:
            continue

    return players


async def fetch_player_stats() -> list[PlayerStats]:
    """Estatísticas gerais (W/D/L, GF/GA, médias, pontos)."""
    html = await _fetch_html()
    players = _parse_player_stats(html)
    logger.info("Totalcorner stats: %d jogadores", len(players))
    return players


async def fetch_goal_stats() -> list[PlayerGoalStats]:
    """Estatísticas de gols e porcentagens over (1.5 a 10.5)."""
    html = await _fetch_html()
    players = _parse_goal_stats(html)
    logger.info("Totalcorner goal stats: %d jogadores", len(players))
    return players


def invalidate_cache() -> None:
    global _cache_html, _cache_ts
    _cache_html = None
    _cache_ts = 0.0
