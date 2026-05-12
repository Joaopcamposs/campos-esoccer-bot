# Architecture — FastAPI Telegram Base

## Visão Geral

App minimalista para **scraping web + envio/edição de mensagens Telegram**.
Combina FastAPI (HTTP/API) com Telegram Bot (polling/webhook) e scheduler para rotinas periódicas.
Projetado para rodar em **256MB RAM**, sem autenticação.

```
┌───────────────────────────────────────────────────────────┐
│                       FastAPI App                          │
│                                                            │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐       │
│  │ /health  │  │ /api/*   │  │ /webhook/telegram  │       │
│  └──────────┘  └────┬─────┘  └────────┬───────────┘       │
│                     │                 │                    │
│              ┌──────▼─────────────────▼────────────┐      │
│              │       telegram/service.py           │      │
│              │  envio + persistência + status      │      │
│              └──────┬─────────────────┬────────────┘      │
│                     │                 │                    │
│  ┌──────────┐┌──────▼──────┐   ┌──────▼────────────┐     │
│  │scheduler ││ client.py   │   │  models.py        │     │
│  │  + jobs  ││ (httpx)     │   │ (SentMessage)     │     │
│  └────┬─────┘└──────┬──────┘   └──────┬────────────┘     │
│       │             │                 │                    │
└───────┼─────────────┼─────────────────┼────────────────────┘
        │             │                 │
        │     ┌───────▼──┐       ┌──────▼─────┐
        └────►│ Telegram  │       │ PostgreSQL │
              │ Bot API   │       │  :54311    │
              └───────────┘       └────────────┘
```

## Estrutura de Arquivos

```
app/
  main.py                  → Entry point, lifespan, rotas HTTP
  scheduler.py             → Scheduler para rotinas periódicas
  infra/
    config.py              → Settings via pydantic-settings (.env)
    database.py            → Engine async + session factory
    models.py              → Base entity + SentMessage (UUID7, status)
  telegram/
    client.py              → Cliente HTTP (httpx) → Telegram API (retry + HTML)
    handler.py             → Processa updates (polling ou webhook)
    polling.py             → Long polling para dev local
    service.py             → Envio/edição com persistência e status
  jobs/
    __init__.py            → Registro de todos os jobs
    example.py             → Job modelo (heartbeat a cada 5 min)
tests/                     → Testes unitários (90%+ coverage, SQLite em memória)
scripts/
  setup.sh                 → Setup automático (bot + banco + validação)
  validate.sh              → Validação envio/edição com dados mock
Dockerfile                 → Multi-stage build otimizado
docker-compose.yml         → App :8011 + Postgres :54311 (256MB limit)
Makefile                   → Comandos dev/prod/setup/validate
```

## Portas

| Serviço | Porta externa | Porta interna |
|---------|---------------|---------------|
| FastAPI | 8011 | 8000 |
| PostgreSQL | 54311 | 5432 |

Portas não-padrão para evitar conflito com outros serviços locais.

## PYTHONPATH

O projeto usa `PYTHONPATH=app` para que imports como `from infra.config` e `from app.telegram` funcionem.
Já configurado em: Makefile, Dockerfile, pytest.ini e scripts.

---

## Fluxo de Scraping → Telegram

Fluxo principal do app. Scraper coleta dados, envia mensagem "carregando" e depois edita com resultado.

### Passo a passo

```
1. Scraper inicia
   └→ send_and_store(chat_id, "⏳ Carregando...", reference_key="btc-daily")
   └→ Telegram recebe mensagem
   └→ SentMessage salvo: status="pending", id=UUID7

2. Scraping executa (segundos a minutos)
   └→ httpx busca dados de sites
   └→ Processa/formata resultado

3. Scraper finaliza com sucesso
   └→ edit_by_reference("btc-daily", "📊 BTC: $104.250 ...")
   └→ Telegram edita mensagem existente
   └→ SentMessage atualizado: status="done"

4. Ou scraper falha
   └→ mark_error("btc-daily", "timeout na API")
   └→ SentMessage atualizado: status="error", error_detail="timeout na API"
```

### Em código

```python
from infra.database import async_session
from app.telegram.service import send_and_store, edit_by_reference, mark_error


async def scrape_and_notify(chat_id: int):
    async with async_session() as session:
        await send_and_store(
            session, chat_id,
            "⏳ Cotação BTC — carregando...",
            reference_key="btc-daily",
        )

    try:
        data = await fetch_btc_price()
    except Exception as e:
        async with async_session() as session:
            await mark_error(session, "btc-daily", str(e))
        return

    async with async_session() as session:
        await edit_by_reference(
            session, "btc-daily",
            f"📊 BTC: ${data['price']:,.2f}\n📈 24h: {data['change']}%",
        )
```

### Ciclo de status

```
send_and_store()     →  status = "pending"   (mensagem enviada, aguardando dados)
edit_by_reference()  →  status = "done"      (mensagem editada com dados finais)
mark_error()         →  status = "error"     (falha, com error_detail)
```

Consultar pendentes: `GET /api/pending` ou `await list_pending(session)`.

### Formatação HTML

Mensagens usam `parse_mode=HTML` por padrão. Formatar texto com:

```python
text = "<b>BTC</b>: $104.250\n<i>+2.3% 24h</i>\n<a href='https://...'>fonte</a>"
await client.send_message(chat_id, text)
```

Tags suportadas: `<b>`, `<i>`, `<u>`, `<s>`, `<code>`, `<pre>`, `<a href>`.

### Via endpoints HTTP

```bash
# Envia placeholder (retorna id UUID7 + message_id + status=pending)
curl -X POST "http://localhost:8011/api/send?text=⏳+Carregando...&reference_key=btc-daily"

# Edita com dados finais (status → done)
curl -X PUT "http://localhost:8011/api/edit?reference_key=btc-daily&text=📊+BTC:+$104.250"

# Lista mensagens pendentes
curl "http://localhost:8011/api/pending"
```

### Validação rápida

```bash
make validate   # envia 2 mensagens mock (BTC + ETH) e edita após 2s
```

---

## Scheduler (Rotinas Periódicas)

Scheduler interno baseado em asyncio — sem dependências externas (sem celery, sem APScheduler).
Inicia no lifespan, cancela no shutdown. Se um job falha, loga o erro e continua no próximo ciclo.

### Como funciona

```python
# app/scheduler.py
@register("nome-do-job", interval_seconds=300)
async def meu_job():
    ...
```

O decorator `@register` adiciona o job à lista. `start_all()` no lifespan cria uma `asyncio.Task` por job. `stop_all()` cancela tudo no shutdown.

### Criar novo job

1. Crie arquivo em `app/jobs/`:

```python
# app/jobs/crypto_scraper.py
import httpx

from app.scheduler import register
from app.telegram.service import send_and_store, edit_by_reference, mark_error
from infra.config import settings
from infra.database import async_session


@register("crypto-scraper", interval_seconds=300)
async def scrape_crypto():
    ref_key = "btc-latest"

    async with async_session() as session:
        await send_and_store(
            session, settings.telegram_channel_id,
            "⏳ Atualizando BTC...",
            reference_key=ref_key,
        )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://api.example.com/btc")
            data = resp.json()
    except Exception as e:
        async with async_session() as session:
            await mark_error(session, ref_key, str(e))
        return

    async with async_session() as session:
        await edit_by_reference(
            session, ref_key,
            f"<b>BTC</b>: ${data['price']:,.2f}\n📈 {data['change']}%",
        )
```

2. Registre no `app/jobs/__init__.py`:

```python
from app.jobs import example, crypto_scraper  # noqa: F401
```

Pronto — roda automaticamente a cada 5 minutos.

### Job existente (exemplo)

`app/jobs/example.py` — heartbeat que loga a cada 5 min. Substitua ou delete.

---

## Polling vs Webhook

O bot suporta dois modos de receber updates do Telegram, controlado por `TELEGRAM_POLLING` no `.env`.

### Polling (padrão, dev local)

```
TELEGRAM_POLLING=true
```

Bot busca updates ativamente via long polling (`getUpdates`). Não precisa de URL pública, ngrok ou túnel. Ideal para desenvolvimento local.

```
App inicia
  └→ delete_webhook()          (limpa webhook anterior)
  └→ loop: getUpdates(timeout=30)
       └→ handle_update() para cada update
       └→ offset avança (não reprocessa)
```

O polling roda como `asyncio.Task` dentro do lifespan — não bloqueia o FastAPI. Se falhar, loga o erro, espera 3s e reconecta.

### Webhook (produção)

```
TELEGRAM_POLLING=false
```

Telegram envia updates via POST para `/webhook/telegram`. Requer URL pública com HTTPS.

```bash
# Configurar webhook após deploy
curl "https://api.telegram.org/bot<TOKEN>/setWebhook\
  ?url=https://<APP_URL>/webhook/telegram\
  &secret_token=<SECRET>"
```

O `TELEGRAM_WEBHOOK_SECRET` valida cada request via header `X-Telegram-Bot-Api-Secret-Token` (comparação constant-time).

### Quando usar qual

| Modo | Quando usar | `TELEGRAM_POLLING` |
|------|------------|-------------------|
| **Polling** | Dev local, sem URL pública | `true` |
| **Webhook** | Produção, deploy com HTTPS | `false` |

### Logs

Ambos os modos logam cada update recebido:

```
14:32:01 INFO     app.telegram.handler — Update recebido: chat_id=123 type=private user=joao text='hello'
14:32:01 INFO     app.telegram.client — Enviando mensagem para chat_id=123
```

---

## Logging

Logging configurável via `LOG_LEVEL` no `.env` (`DEBUG`, `INFO`, `WARNING`, `ERROR`).

```
LOG_LEVEL=INFO      # padrão
LOG_LEVEL=DEBUG     # verbose — inclui payloads de API e queries
```

Cada módulo loga suas ações:

| Módulo | O que loga |
|--------|-----------|
| `main` | Lifespan (banco, polling/webhook, shutdown) |
| `client` | Chamadas API, retry 429, open/close |
| `handler` | Updates recebidos (chat, user, texto) |
| `service` | Mensagens armazenadas, editadas, erros |
| `scheduler` | Jobs iniciados, falhas |
| `polling` | Loop iniciado, erros de conexão |

Formato: `HH:MM:SS LEVEL    module — mensagem`

---

## Camadas

| Camada | Arquivo | Responsabilidade |
|--------|---------|------------------|
| **HTTP** | `app/main.py` | Rotas, lifespan, webhook, scheduler |
| **Scheduler** | `app/scheduler.py` | Registro e execução de jobs periódicos |
| **Jobs** | `app/jobs/*.py` | Rotinas periódicas (scrapers, notificações) |
| **Service** | `app/telegram/service.py` | Envio/edição + persistência + status |
| **Client** | `app/telegram/client.py` | Telegram Bot API (retry 429 + HTML) |
| **Polling** | `app/telegram/polling.py` | Long polling para dev local |
| **Handler** | `app/telegram/handler.py` | Processamento de updates recebidos |
| **Model** | `app/infra/models.py` | Entidades SQLAlchemy 2.0 |
| **Config** | `app/infra/config.py` | Variáveis de ambiente |
| **Database** | `app/infra/database.py` | Engine async + session factory |

Dependência flui para baixo: HTTP → Service → Client/Model. Nunca para cima.

---

## Banco de Dados

SQLAlchemy 2.0 async com asyncpg. Pool fixo: `pool_size=5`, `max_overflow=5`.

**TimestampMixin** — `created_at`/`updated_at` automáticos em todas entidades.

**SentMessage** — Armazena tudo que foi enviado:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | UUID7 (str, PK) | Ordenável por tempo, sem colisão |
| `chat_id` | bigint | ID do canal/chat Telegram |
| `message_id` | bigint | ID da mensagem no Telegram |
| `content_type` | str | `"text"` ou `"photo"` |
| `status` | str | `"pending"` → `"done"` ou `"error"` |
| `error_detail` | str (nullable) | Detalhe do erro quando `status="error"` |
| `reference_key` | str (nullable, indexed) | Chave de negócio para edição |
| `created_at` | datetime (tz) | Timestamp criação |
| `updated_at` | datetime (tz) | Timestamp última atualização |

Tabelas criadas automaticamente no lifespan. Para produção, migrar para **Alembic**.

---

## Telegram Client

`app/telegram/client.py` — cliente HTTP leve via httpx com:

- **`parse_mode=HTML`** por padrão em `send_message`, `edit_message_text`, `send_photo`
- **Retry automático** em 429 (rate limit) — respeita `retry_after`, até 3 tentativas
- **Singleton** — reutiliza conexões TCP via `httpx.AsyncClient`

Funções disponíveis:

| Função | Descrição |
|--------|-----------|
| `send_message(chat_id, text)` | Envia texto |
| `edit_message_text(chat_id, message_id, text)` | Edita texto |
| `send_photo(chat_id, photo, caption)` | Envia foto (URL ou file_id) |
| `edit_message_media(chat_id, message_id, media)` | Edita mídia |
| `api_call(method, **kwargs)` | Chamada genérica |
| `get_updates(offset, timeout)` | Long polling (usado por `polling.py`) |
| `delete_webhook()` | Remove webhook para ativar polling |

---

## Telegram Handler

`app/telegram/handler.py` — processa updates (polling ou webhook, mesmo handler).

Comandos implementados:

| Comando | Resposta |
|---------|----------|
| `/start` | "Bot ativo." |
| `/ping` | "pong" |
| qualquer outro | "Bot operando em modo automático. Comandos: /start /ping" |

Para adicionar comando:

```python
if text.startswith("/cotacao"):
    await client.send_message(chat_id, "<b>BTC</b>: $104.250")
    return
```

---

## Testes

90%+ coverage. Testes rodam isolados — **nunca tocam banco Postgres ou Telegram API**.

- **Banco**: SQLite em memória via `aiosqlite`
- **Telegram**: mock completo via `unittest.mock`
- **Segurança extra**: `DATABASE_URL` forçado pra `localhost:1` (porta inválida) no conftest — se algum código vazar da fixture, falha com connection refused

```bash
make test   # pytest -x --tb=short -q --cov=app --cov-report=term-missing
```

---

## Otimizações (256MB)

- **httpx singleton** — reutiliza conexões TCP
- **Pool pequeno** — 5+5 conexões (suficiente para bot)
- **uvloop** — event loop otimizado em C
- **--no-access-log** — reduz I/O em produção
- **Multi-stage Docker** — imagem final sem build tools
- **expire_on_commit=False** — evita lazy loads desnecessários
- **UUID7** — ordenável por tempo, gerado no app (sem roundtrip ao banco)

---

## Como Expandir

### Adicionar novo scraper como job periódico

Ver seção [Scheduler](#scheduler-rotinas-periódicas) acima.

### Adicionar novo model

Herde `TimestampMixin` + `Base` em `app/infra/models.py`:

```python
class Alert(TimestampMixin, Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid7)
    name: Mapped[str]
    active: Mapped[bool] = mapped_column(default=True)
```

### Adicionar novo endpoint

Crie router e registre no `app/main.py`:

```python
# app/routes/alerts.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from infra.database import get_session

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

@router.get("/")
async def list_alerts(session: AsyncSession = Depends(get_session)):
    ...

# app/main.py
from app.routes.alerts import router as alerts_router
app.include_router(alerts_router)
```

### Adicionar Alembic (migrações)

```bash
uv add alembic
uv run alembic init alembic
```

Configurar `alembic/env.py` com async engine e `Base.metadata`.

---

## Deploy

### FastAPI Cloud

```bash
# 1. Deploy
make deploy

# 2. Configurar webhook Telegram
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<APP_URL>/webhook/telegram&secret_token=<SECRET>"
```

Entry point: `app.main:app`. Variáveis de ambiente configuradas no painel.

### Docker (qualquer cloud)

```bash
docker build -t fastapi-telegram-base .
docker run -p 8011:8000 --env-file .env fastapi-telegram-base
```

Compatível com: Railway, Render, Fly.io, Cloud Run, ECS.

---

## Comandos Make

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
