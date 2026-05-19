# eSoccer Battle Bot

Bot automatizado para palpites de **eSoccer Battle 8 minutos** (FIFA). Executa a cada 4 minutos: coleta jogos próximos, gera previsão de gols cruzando dados locais e externos, envia palpite no Telegram e atualiza com resultado final (✅/❌).

## Stack

- **Python 3.14** / **uv** / **ruff**
- **FastAPI** com lifespan e uvloop
- **SQLAlchemy 2.0** async com asyncpg (Postgres)
- **httpx** como cliente HTTP (Telegram API + scraping)
- **BeautifulSoup + lxml** para parsing HTML
- **Docker** multi-stage com limite 256MB RAM
- **Scheduler** interno (asyncio) para rotinas periódicas

## Quick Start

```bash
# 1. Instalar dependências
make install

# 2. Copiar e configurar variáveis
cp .env.example .env
# Preencha: TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

# 3. Subir banco
docker compose up postgres -d

# 4. Rodar app
make dev

# 5. Testar scraping
curl "http://localhost:8011/api/upcoming"
curl "http://localhost:8011/api/player-stats"
curl "http://localhost:8011/api/goal-stats"
curl "http://localhost:8011/api/results"
```

## Como Funciona

```
┌─────────────────────────────────────────────────────────────────┐
│                    Ciclo a cada 4 minutos                       │
│                                                                 │
│  1. Scrap tipmanager ──→ jogos próximos 10 min                  │
│  2. Scrap totalcorner (cache 30s) ──→ stats + over%            │
│  3. Motor de palpites ──→ expected goals + linha over           │
│  4. Envia no Telegram ──→ salva Prediction (match_key único)   │
│  5. Scrap tipmanager ──→ resultados finalizados                 │
│  6. Edita mensagem com ✅/❌ + atualiza PlayerMatch            │
└─────────────────────────────────────────────────────────────────┘
```

### Fontes de dados

| Fonte | URL | Dados |
|-------|-----|-------|
| **tipmanager** | `tipmanager.net/pt/sports/e-soccer/leagues/1/battle` | Próximos jogos + resultados finalizados (fonte única) |
| **totalcorner** | `totalcorner.com/league/view/12995/end/...` | Stats (W/D/L, GF/GA), over% (1.5–10.5) |
| **banco local** | `player_match` | Histórico individual por jogador (atualizado a cada resultado) |

### Motor de palpites

Para cada jogador no confronto:
1. Se tem **20+ jogos** no banco local → usa médias locais
2. Senão → usa stats externas do totalcorner
3. Sem dados → fallback conservador (avg 2.8 GF / 2.5 GA)

Cálculo:
```
home_expected = (home_avg_gf + away_avg_ga) / 2
away_expected = (away_avg_gf + home_avg_ga) / 2
expected_total = home_expected + away_expected
over_line = int(expected_total - 1) + 0.5  (mínimo 1.5)
```

### Mensagem no Telegram

```
E-soccer Battle 8 minutos - LIVE @1.5+

🎯 Grellz (France) vs Simaponika (Germany)
⚽️ Gols esperado: 5.80
🥅 Over 4.5 gols
🕒 14:00

Análise:
Grellz: [média marcada: 3.60 | média sofrida: 2.40]
Simaponika: [média marcada: 3.00 | média sofrida: 2.60]
Frequência de gols acima de 4.5 (75%)
```

Após resultado:
```
...
Resultado: 3 - 2 (total: 5)

✅
```

## Estrutura

```
app/
  main.py                  → Entry point, lifespan, webhook
  routes.py                → Endpoints API (/api/*)
  scheduler.py             → Scheduler asyncio para jobs periódicos
  prediction.py            → Motor de palpites (cruza dados locais/externos)
  scrapers/
    tipmanager.py          → Scrap próximos jogos + resultados (fonte única)
    totalcorner.py         → Scrap stats, over% (cache 30s)
  jobs/
    esoccer.py             → Job principal (ciclo completo a cada 4min)
    example.py             → Job modelo (heartbeat)
  infra/
    config.py              → Settings via pydantic-settings (.env)
    database.py            → Engine async + session factory
    models.py              → SentMessage, PlayerLocalStats, Prediction
  telegram/
    client.py              → Cliente HTTP → Telegram API (retry + HTML)
    handler.py             → Processa updates (polling ou webhook)
    polling.py             → Long polling para dev local
    service.py             → Envio/edição com persistência e status
tests/                     → Testes unitários (SQLite em memória)
```

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/upcoming?window=10` | Próximos jogos eSoccer (BRT) |
| `GET` | `/api/player-stats?player=Grellz` | Stats consolidadas (totalcorner) |
| `GET` | `/api/goal-stats?player=Grellz` | Over% por jogador (totalcorner) |
| `GET` | `/api/results?player=Grellz` | Resultados recentes (tipmanager) |
| `POST` | `/api/send` | Envia mensagem ao canal |
| `PUT` | `/api/edit` | Edita mensagem por `reference_key` |
| `GET` | `/api/pending` | Mensagens pendentes |
| `POST` | `/webhook/telegram` | Webhook Telegram (interno) |

## Banco de Dados

### PlayerLocalStats

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `player` | str (PK) | Nome do jogador |
| `matches_played` | int | Total de partidas |
| `goals_for` | int | Gols marcados |
| `goals_against` | int | Gols sofridos |
| `wins/draws/losses` | int | Resultados |
| `avg_goals_for` | property | `goals_for / matches_played` |
| `avg_goals_against` | property | `goals_against / matches_played` |

### Prediction

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | UUID7 | PK |
| `match_key` | str (unique) | Deduplicação: `YYYYMMDD_HHMM_player1_player2` |
| `kickoff_brt` | datetime | Horário do jogo (BRT) |
| `home/away_team` | str | Seleções |
| `home/away_player` | str | Jogadores |
| `expected_total_goals` | float | Previsão de gols totais |
| `over_line` | float | Linha over recomendada |
| `message_id` | bigint | ID da mensagem no Telegram |
| `status` | str | `pending` → `done` |
| `home/away_goals` | int | Resultado real |
| `success` | bool | `total_goals > over_line` |

## Variáveis de Ambiente

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `TELEGRAM_BOT_TOKEN` | Token do @BotFather | `123456:ABC-DEF` |
| `TELEGRAM_WEBHOOK_SECRET` | Secret para webhook | `openssl rand -hex 32` |
| `TELEGRAM_CHANNEL_ID` | ID do canal alvo | `-1001234567890` |
| `DATABASE_URL` | Connection string Postgres | `postgresql+asyncpg://app:app@localhost:54311/app` |
| `TELEGRAM_POLLING` | `true` = polling, `false` = webhook | `true` |
| `LOG_LEVEL` | Nível de log | `INFO` |

## Comandos

| Comando | Descrição |
|---------|-----------|
| `make install` | Instala dependências via uv |
| `make dev` | Servidor local com reload (:8011) |
| `make run` | Servidor produção local (:8011) |
| `make test` | Testes com coverage |
| `make lint` | Ruff check |
| `make format` | Auto-format com ruff |
| `make up` | Docker compose up |
| `make down` | Docker compose down |
| `make clean` | Remove volumes e cache |
| `make resetdb` | Recria banco do zero |

## Testes

```bash
make test
```

Testes rodam em **SQLite em memória** — Postgres nunca é tocado. Telegram API mockada. Scrapers testados com HTML fixture.
