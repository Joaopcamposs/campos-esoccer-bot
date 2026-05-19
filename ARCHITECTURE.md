# Architecture — eSoccer Battle Bot

## Visão Geral

Bot automatizado para palpites eSoccer Battle 8 minutos.
Combina FastAPI (HTTP/API) + scraping (tipmanager, totalcorner) + motor de palpites + Telegram Bot.
Projetado para rodar em **256MB RAM**.

```
┌──────────────────────────────────────────────────────────────────────┐
│                           FastAPI App                                │
│                                                                      │
│  ┌────────────┐  ┌────────────────┐  ┌────────────────────┐         │
│  │ /api/health│  │ /api/upcoming  │  │ /webhook/telegram  │         │
│  │ /api/stats │  │ /api/results   │  └────────┬───────────┘         │
│  └────────────┘  └───────┬────────┘           │                     │
│                          │                    │                      │
│  ┌───────────────────────▼────────────────────▼──────────────┐      │
│  │                    Scrapers                                │      │
│  │  tipmanager.py ─── próximos jogos + resultados            │      │
│  │  totalcorner.py ─── stats + over% (cache 30s)             │      │
│  └───────────────────────┬───────────────────────────────────┘      │
│                          │                                           │
│  ┌───────────────────────▼───────────────────────────────────┐      │
│  │                  prediction.py                             │      │
│  │  PlayerLocalStats (20+ jogos) → dados locais              │      │
│  │  totalcorner stats           → dados externos (fallback)  │      │
│  │  → expected_total_goals + over_line                       │      │
│  └───────────────────────┬───────────────────────────────────┘      │
│                          │                                           │
│  ┌──────────┐ ┌──────────▼──────┐  ┌──────────────────────┐        │
│  │scheduler │ │ telegram/       │  │  infra/models.py     │        │
│  │ + jobs   │ │ client+service  │  │  Prediction          │        │
│  └────┬─────┘ └──────┬──────────┘  │  PlayerLocalStats    │        │
│       │              │              │  SentMessage         │        │
└───────┼──────────────┼──────────────┼──────────────────────┘        │
        │              │              │                                │
        │      ┌───────▼──┐    ┌─────▼──────┐                        │
        └─────►│ Telegram  │    │ PostgreSQL │                        │
               │ Bot API   │    │  :54311    │                        │
               └───────────┘    └────────────┘
```

## Ciclo Principal (Job esoccer-battle, 240s)

```
1. fetch_upcoming_matches(10min)
   └→ tipmanager: HTML → lista de Match(kickoff, teams, players)

2. Para cada match (deduplicação via match_key):
   └→ generate_prediction(session, match)
      ├→ _get_local_stats(player) — banco local
      ├→ fetch_player_stats() — totalcorner (cache)
      ├→ fetch_goal_stats() — totalcorner (cache)
      └→ PredictionResult(expected_total, over_line, over_pct)

3. send_message(chat_id, texto formatado)
   └→ Prediction salvo: status=pending, message_id=X

4. fetch_results()
   └→ tipmanager: resultados finalizados

5. Para cada Prediction pendente com resultado:
   └→ editMessageText com resultado + ✅/❌
   └→ _update_local_stats(home_player, away_player)
   └→ Prediction: status=done, success=True/False
```

## Estrutura de Arquivos

```
app/
  main.py                  → Entry point, lifespan, webhook
  routes.py                → APIRouter /api/* (upcoming, stats, results, etc)
  scheduler.py             → Registro e execução de jobs periódicos
  prediction.py            → Motor de palpites (local vs external vs default)
  scrapers/
    __init__.py
    tipmanager.py          → Scrap próximos jogos + resultados (fonte única)
    totalcorner.py         → Scrap stats, over% (cache 30s)
  jobs/
    __init__.py            → Registro de todos os jobs
    esoccer.py             → Job principal (ciclo completo)
    example.py             → Job modelo (heartbeat)
  infra/
    config.py              → Settings via pydantic-settings (.env)
    database.py            → Engine async + session factory
    models.py              → SentMessage, PlayerLocalStats, Prediction
  telegram/
    client.py              → Cliente HTTP (httpx) → Telegram API
    handler.py             → Processa updates do Telegram
    polling.py             → Long polling para dev local
    service.py             → Envio/edição com persistência + status
tests/
  test_tipmanager.py       → Parsing HTML tipmanager + filtro por janela
  test_totalcorner.py      → Parsing stats/goals + cache
  test_prediction.py       → Motor de palpites (external/default)
  test_esoccer_job.py      → Formatação e match_key
  test_*.py                → Testes base (handler, service, endpoints, etc)
```

## Scrapers

### tipmanager.py

- **Fonte**: `tipmanager.net/pt/sports/e-soccer/leagues/1/battle`
- **2 tabelas** na página:
  1. Tabela 1 — Próximos jogos (data, jogadores, times)
  2. Tabela 2 — Resultados finalizados (data, jogadores, times, placar)
- **Sem cache** (dados mudam a cada minuto)
- **Timezone**: horários vêm em UTC, convertidos para BRT
- **Parsing**: `aria-label` dos links contém "Player - Team - Clique..."
- **Formato data**: `DD/MM/YYYY, HH:MM` (UTC)

### totalcorner.py

- **Fonte**: HTML server-side
- **2 tabelas** extraídas (stats apenas, resultados agora vêm do tipmanager):
  1. `stats_table[0]` — Player Statistics (MP, W/D/L, GF/GA, avg, points)
  2. `stats_table[1]` — Total Goals Statistics (MP, avg GF/GA, over 1.5–10.5 %)
- **Cache**: HTML em memória, TTL 30s, compartilhado entre as funções
- **Timezone**: configurável via `TOTALCORNER_TIMEZONE` (default `Europe/London`, BST no verão = GMT+1)

## Motor de Palpites

### Hierarquia de dados

```
1. Dados locais (PlayerLocalStats, 20+ jogos) ←── melhor
2. Dados externos (totalcorner PlayerStats)   ←── fallback
3. Valores default (2.8 GF / 2.5 GA)         ←── último recurso
```

### Cálculo

```python
home_expected = (home_avg_gf + away_avg_ga) / 2
away_expected = (away_avg_gf + home_avg_ga) / 2
expected_total = home_expected + away_expected
over_line = max(1.5, int(expected_total - 1) + 0.5)
```

### Deduplicação

`match_key = f"{kickoff:%Y%m%d_%H%M}_{home_player}_{away_player}"`

Constraint `UNIQUE` no banco. Se `match_key` já existe, palpite é ignorado.

## Banco de Dados

SQLAlchemy 2.0 async com asyncpg. Pool: `pool_size=5`, `max_overflow=5`.

### Tabelas

| Tabela | PK | Descrição |
|--------|-----|-----------|
| `sent_messages` | UUID7 | Mensagens enviadas (Telegram message_id + status) |
| `player_local_stats` | player (str) | Stats acumuladas por jogador |
| `predictions` | UUID7 | Palpites (match_key único, resultado, sucesso) |

Tabelas criadas automaticamente no lifespan via `Base.metadata.create_all`.
Schema isolado via `DB_SCHEMA` (default `esoccer_bot`) — permite multi-tenant no mesmo banco.

## Portas

| Serviço | Porta externa | Porta interna |
|---------|---------------|---------------|
| FastAPI | 8011 | 8000 |
| PostgreSQL | 54311 | 5432 |

## Camadas

| Camada | Arquivo | Responsabilidade |
|--------|---------|------------------|
| **HTTP** | `main.py` | Lifespan, webhook, inclui router |
| **API** | `routes.py` | Endpoints de negócio |
| **Scheduler** | `scheduler.py` | Registro e execução de jobs |
| **Jobs** | `jobs/*.py` | Rotinas periódicas |
| **Prediction** | `prediction.py` | Lógica de palpites |
| **Scrapers** | `scrapers/*.py` | Coleta de dados externos |
| **Service** | `telegram/service.py` | Envio/edição + persistência |
| **Client** | `telegram/client.py` | Telegram Bot API (retry 429) |
| **Model** | `infra/models.py` | Entidades SQLAlchemy |
| **Config** | `infra/config.py` | Variáveis de ambiente |
| **Database** | `infra/database.py` | Engine async + session |

Dependência flui para baixo. Nunca para cima.

## Polling vs Webhook

| Modo | Quando usar | `TELEGRAM_POLLING` |
|------|------------|-------------------|
| **Polling** | Dev local, sem URL pública | `true` |
| **Webhook** | Produção, deploy com HTTPS | `false` |

## Timezone

Horários internos sempre em **BRT** (`America/Sao_Paulo`). Conversão na entrada:

| Fonte | Timezone origem | Observação |
|-------|----------------|------------|
| tipmanager | UTC | Horários no HTML são UTC, convertidos para BRT |
| totalcorner | `TOTALCORNER_TIMEZONE` (default `Europe/London`) | BST (GMT+1) no verão |

**Como calibrar**:
1. Acessar `/api/debug/tipmanager-raw`
2. Comparar horários com `server_now_brt`

Pontos de conversão:
- `tipmanager.py`: UTC → BRT no `kickoff` de cada `Match` e `MatchResult`
- `totalcorner.py`: `SITE_TZ` → BRT (usado apenas para stats externas)
- `esoccer.py`: `_make_match_key` força BRT, `_format_brt_time` força BRT
- `update_results`: usa `pred.kickoff_brt` (original) na mensagem editada, nunca o horário do resultado

## Proteções no update_results

- Predictions com `kickoff_brt > agora` são ignoradas (jogo futuro)
- Match por `home_player + away_player` (case-insensitive)
- Horário da mensagem editada preserva o `kickoff_brt` original da prediction

## Variáveis de Ambiente

| Variável | Obrigatória | Default | Descrição |
|----------|-------------|---------|-----------|
| `TELEGRAM_BOT_TOKEN` | Sim | `""` | Token do bot |
| `TELEGRAM_CHANNEL_ID` | Sim | `0` | ID do canal (começa com -100) |
| `TELEGRAM_WEBHOOK_SECRET` | Não | `""` | Secret pra validar webhook |
| `DATABASE_URL` | Sim | `postgresql+asyncpg://...` | URL do banco (aceita `postgresql://`, converte auto) |
| `TELEGRAM_POLLING` | Não | `true` | `true`=dev local, `false`=prod webhook |
| `LOG_LEVEL` | Não | `INFO` | Nível de log |
| `TOTALCORNER_TIMEZONE` | Não | `Europe/London` | Timezone dos horários do totalcorner |
| `DB_SCHEMA` | Não | `esoccer_bot` | Schema PostgreSQL (vazio=public) |
