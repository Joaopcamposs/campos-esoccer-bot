#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="$(dirname "$0")/../.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ .env não encontrado. Copie .env.example → .env e preencha TELEGRAM_BOT_TOKEN"
    exit 1
fi

source "$ENV_FILE"

if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ "$TELEGRAM_BOT_TOKEN" = "your-bot-token" ]; then
    echo "❌ TELEGRAM_BOT_TOKEN não configurado no .env"
    exit 1
fi

API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"

# 1. Verificar bot
echo "🔍 Verificando bot..."
BOT_INFO=$(curl -sf "$API/getMe")
BOT_NAME=$(echo "$BOT_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['username'])")
echo "✅ Bot: @${BOT_NAME}"

# 2. Descobrir channel ID
echo ""
echo "📢 Buscando channel ID nos updates..."
echo "   (bot precisa ser admin do canal + alguém postou algo)"
UPDATES=$(curl -sf "$API/getUpdates")
CHANNEL_ID=$(echo "$UPDATES" | python3 -c "
import sys, json
data = json.load(sys.stdin)['result']
for u in data:
    for key in ('channel_post', 'my_chat_member', 'message'):
        chat = u.get(key, {}).get('chat', {})
        if chat.get('type') in ('channel', 'supergroup'):
            print(chat['id'])
            sys.exit(0)
print('')
" 2>/dev/null || echo "")

if [ -z "$CHANNEL_ID" ]; then
    echo "⚠️  Nenhum canal encontrado nos updates."
    echo "   1. Adicione o bot como admin do canal"
    echo "   2. Poste qualquer mensagem no canal"
    echo "   3. Rode este script novamente"
    exit 1
fi
echo "✅ Channel ID: ${CHANNEL_ID}"

# 3. Gerar webhook secret
echo ""
echo "🔑 Gerando webhook secret..."
WEBHOOK_SECRET=$(openssl rand -hex 32)
echo "✅ Secret gerado"

# 4. Atualizar .env
echo ""
echo "📝 Atualizando .env..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s|^TELEGRAM_CHANNEL_ID=.*|TELEGRAM_CHANNEL_ID=${CHANNEL_ID}|" "$ENV_FILE"
    sed -i '' "s|^TELEGRAM_WEBHOOK_SECRET=.*|TELEGRAM_WEBHOOK_SECRET=${WEBHOOK_SECRET}|" "$ENV_FILE"
else
    sed -i "s|^TELEGRAM_CHANNEL_ID=.*|TELEGRAM_CHANNEL_ID=${CHANNEL_ID}|" "$ENV_FILE"
    sed -i "s|^TELEGRAM_WEBHOOK_SECRET=.*|TELEGRAM_WEBHOOK_SECRET=${WEBHOOK_SECRET}|" "$ENV_FILE"
fi
echo "✅ .env atualizado"

# 5. Subir postgres
echo ""
echo "🐘 Subindo PostgreSQL..."
docker compose up postgres -d --wait
echo "✅ Postgres rodando"

# 6. Subir app
echo ""
echo "🚀 Subindo app em dev mode..."
echo "   Aguardando servidor iniciar..."
PYTHONPATH=app uv run uvicorn app.main:app --reload --port 8011 &
APP_PID=$!
sleep 3

if ! kill -0 $APP_PID 2>/dev/null; then
    echo "❌ App falhou ao iniciar"
    exit 1
fi
echo "✅ App rodando (PID: $APP_PID)"

# 7. Testar envio
echo ""
echo "📤 Testando envio de mensagem..."
SEND_RESULT=$(curl -sf -X POST "http://localhost:8011/api/send?text=Setup+completo&reference_key=setup-test")
echo "✅ Envio: $SEND_RESULT"

# 8. Testar edição
echo ""
echo "✏️  Testando edição de mensagem..."
sleep 1
EDIT_RESULT=$(curl -sf -X PUT "http://localhost:8011/api/edit?reference_key=setup-test&text=Setup+completo+%E2%9C%85+editado")
echo "✅ Edição: $EDIT_RESULT"

# 9. Testar health
echo ""
echo "💚 Health check..."
HEALTH=$(curl -sf "http://localhost:8011/health")
echo "✅ Health: $HEALTH"

# Encerrar app
echo ""
kill $APP_PID 2>/dev/null
echo "🛑 App encerrado"

echo ""
echo "═══════════════════════════════════════"
echo "  Setup completo!"
echo "  Bot: @${BOT_NAME}"
echo "  Canal: ${CHANNEL_ID}"
echo "  Comandos:"
echo "    make dev    → servidor com reload"
echo "    make up     → docker compose (prod)"
echo "    make test   → rodar testes"
echo "═══════════════════════════════════════"
