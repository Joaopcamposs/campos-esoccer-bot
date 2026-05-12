"""Scraper aceodds — próximos jogos eSoccer Battle 8min."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

URL = (
    "https://www.aceodds.com/pt/bet365-transmissao-ao-vivo"
    "/futebol/e-soccer-battle-8-minutos-de-jogo.html"
)

BRT = ZoneInfo("America/Sao_Paulo")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

_MATCH_RE = re.compile(r"^(.+?)\s*\(([^)]+)\)\s*x\s*(.+?)\s*\(([^)]+)\)$")


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


def _parse_date_header(text: str, fallback_date: datetime) -> datetime:
    """Extrai data do header 'Ter, 12 Maio 2026 - Partidas de Hoje' ou similar."""
    cleaned = text.split(" - ")[0].strip()
    cleaned = re.sub(r"^[A-Za-zÀ-ú]+,\s*", "", cleaned)

    months_pt = {
        "janeiro": "01",
        "fevereiro": "02",
        "março": "03",
        "marco": "03",
        "abril": "04",
        "maio": "05",
        "junho": "06",
        "julho": "07",
        "agosto": "08",
        "setembro": "09",
        "outubro": "10",
        "novembro": "11",
        "dezembro": "12",
    }
    for name, num in months_pt.items():
        cleaned = cleaned.lower().replace(name, num)

    parts = cleaned.strip().split()
    if len(parts) == 3:
        try:
            day, month, year = parts
            return datetime(int(year), int(month), int(day), tzinfo=BRT)
        except ValueError, IndexError:
            pass

    return fallback_date


def _parse_match_text(text: str) -> tuple[str, str, str, str] | None:
    m = _MATCH_RE.match(text.strip())
    if not m:
        return None
    return (
        m.group(1).strip(),
        m.group(2).strip(),
        m.group(3).strip(),
        m.group(4).strip(),
    )


async def fetch_upcoming_matches(window_minutes: int = 5) -> list[Match]:
    """Busca jogos que começam nos próximos `window_minutes` minutos (BRT)."""
    now = datetime.now(BRT)
    cutoff = now + timedelta(minutes=window_minutes)

    logger.info(
        "Buscando jogos aceodds entre %s e %s",
        now.strftime("%H:%M"),
        cutoff.strftime("%H:%M"),
    )

    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
        resp = await client.get(URL)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.select_one("table.table")
    if not table:
        logger.warning("Tabela não encontrada no HTML aceodds")
        return []

    matches: list[Match] = []
    current_date = now

    for row in table.find_all("tr"):
        cells = row.find_all("td")

        # Header de data
        if len(cells) == 1:
            h2 = cells[0].find("h2")
            if h2:
                current_date = _parse_date_header(h2.get_text(), now)
            continue

        if len(cells) < 2:
            continue

        time_text = cells[0].get_text(strip=True)
        if not re.match(r"^\d{1,2}:\d{2}$", time_text):
            continue

        hour, minute = map(int, time_text.split(":"))
        kickoff = current_date.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        if kickoff < now or kickoff > cutoff:
            continue

        link = cells[1].find("a")
        if not link:
            continue

        parsed = _parse_match_text(link.get_text())
        if not parsed:
            continue

        home_team, home_player, away_team, away_player = parsed
        matches.append(
            Match(
                kickoff=kickoff,
                home_team=home_team,
                home_player=home_player,
                away_team=away_team,
                away_player=away_player,
            )
        )

    logger.info(
        "Encontrados %d jogos nos próximos %d min", len(matches), window_minutes
    )
    return matches
