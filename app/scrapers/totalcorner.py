"""Scraper totalcorner — estatísticas consolidadas de jogadores eSoccer Battle 8min."""

import logging
from dataclasses import dataclass

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


def _parse_table_page(html: str) -> list[PlayerStats]:
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table", class_="stats_table")
    if not tables:
        return []
    table = tables[0]

    players: list[PlayerStats] = []
    for row in table.find_all("tr")[1:]:
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


async def fetch_player_stats() -> list[PlayerStats]:
    """Busca estatísticas de jogadores (primeira página — top ~34)."""
    logger.info("Buscando stats totalcorner...")

    async with httpx.AsyncClient(timeout=20.0, headers=HEADERS) as client:
        resp = await client.get(BASE_URL)
        resp.raise_for_status()

    players = _parse_table_page(resp.text)
    logger.info("Totalcorner: %d jogadores extraídos", len(players))
    return players
