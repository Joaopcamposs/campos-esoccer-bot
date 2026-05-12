# FastAPI Telegram Base

Template minimalista para apps de **scraping web + envio/edição de mensagens Telegram**.
FastAPI + SQLAlchemy 2.0 async + httpx. Sem dependências pesadas de bot.

## Stack

- **Python 3.14** / **uv** / **ruff** / **ty**
- **FastAPI** com lifespan e uvloop
- **SQLAlchemy 2.0** async com asyncpg (Postgres)
- **httpx** como cliente HTTP (Telegram API + scraping)
- **Docker** multi-stage com limite 256MB RAM
- **Scheduler** interno para rotinas periódicas
- **Polling + Webhook** — polling automático em dev, webhook em produção

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

# 5. Testar envio
curl -X POST "http://localhost:8011/api/send?text=hello&reference_key=test-1"

# 6. Testar edição
curl -X PUT "http://localhost:8011/api/edit?reference_key=test-1&text=editado"
```

Ou setup automatizado: `make setup` (descobre channel ID, gera secret, testa envio/edição).

## Variáveis de Ambiente

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `TELEGRAM_BOT_TOKEN` | Token do @BotFather | `123456:ABC-DEF` |
| `TELEGRAM_WEBHOOK_SECRET` | Secret para validar webhook | `openssl rand -hex 32` |
| `TELEGRAM_CHANNEL_ID` | ID do canal alvo | `-1001234567890` |
| `DATABASE_URL` | Connection string Postgres async | `postgresql+asyncpg://app:app@localhost:54311/app` |
| `TELEGRAM_POLLING` | `true` = polling (dev), `false` = webhook (prod) | `true` |
| `LOG_LEVEL` | Nível de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Health check |
| `POST` | `/webhook/telegram` | Webhook Telegram (interno) |
| `POST` | `/api/send` | Envia mensagem ao canal (retorna `message_id`, `status`) |
| `PUT` | `/api/edit` | Edita mensagem por `reference_key` |
| `GET` | `/api/pending` | Lista mensagens pendentes de atualização |

## Comandos

| Comando | Descrição |
|---------|-----------|
| `make install` | Instala dependências via uv |
| `make dev` | Servidor local com reload (:8011) |
| `make run` | Servidor produção local (:8011) |
| `make test` | Testes com coverage |
| `make lint` | Ruff + ty check |
| `make format` | Auto-format com ruff |
| `make setup` | Setup completo (bot + banco + validação) |
| `make validate` | Testa envio/edição com dados mock |
| `make up` | Docker compose up |
| `make down` | Docker compose down |
| `make clean` | Remove volumes e cache |
| `make deploy` | Deploy via FastAPI Cloud |

## Testes

```bash
make test
```

Testes rodam em **SQLite em memória** — banco Postgres nunca é tocado. Telegram API mockada via `unittest.mock`. Coverage 90%+.

## Como Usar

Ver [ARCHITECTURE.md](ARCHITECTURE.md) para:
- Polling vs Webhook (quando usar qual)
- Fluxo completo de scraping → envio → edição
- Como criar jobs periódicos (scheduler)
- Como adicionar novos scrapers, models, endpoints e comandos do bot
- Logging (o que cada módulo loga)
- Deploy (FastAPI Cloud + Docker)
