#!/usr/bin/env bash
set -euo pipefail

BASE_URL="http://localhost:8011"

echo "═══════════════════════════════════════"
echo "  Validação: envio + edição Telegram"
echo "═══════════════════════════════════════"
echo ""

# Health check
echo "💚 Health check..."
HEALTH=$(curl -sf "$BASE_URL/health")
echo "   $HEALTH"
echo ""

# Simula scraping: dados iniciais
MOCK_V1="📊 Cotação BTC (carregando...)
━━━━━━━━━━━━━━━━━━━
⏳ Buscando dados...
🕐 $(date '+%H:%M:%S')"

MOCK_V2="📊 Cotação BTC
━━━━━━━━━━━━━━━━━━━
💰 Preço: \$104.250,00
📈 24h: +2.3%
📉 7d: -1.1%
🔄 Volume: \$48.2B
🕐 $(date '+%H:%M:%S')"

# 1. Envia mensagem inicial (simula "carregando")
echo "📤 Enviando mensagem inicial..."
SEND=$(curl -sf -X POST "$BASE_URL/api/send" \
    -G \
    --data-urlencode "text=$MOCK_V1" \
    --data-urlencode "reference_key=btc-price")
echo "   $SEND"
echo ""

# 2. Espera 2s (simula tempo de scraping)
echo "⏳ Simulando scraping (2s)..."
sleep 2
echo ""

# 3. Edita com dados "scrapados"
echo "✏️  Editando com dados atualizados..."
EDIT=$(curl -sf -X PUT "$BASE_URL/api/edit" \
    -G \
    --data-urlencode "reference_key=btc-price" \
    --data-urlencode "text=$MOCK_V2")
echo "   $EDIT"
echo ""

# 4. Segundo ciclo — testa outro reference_key
MOCK_ETH_V1="📊 Cotação ETH (carregando...)
━━━━━━━━━━━━━━━━━━━
⏳ Buscando dados...
🕐 $(date '+%H:%M:%S')"

MOCK_ETH_V2="📊 Cotação ETH
━━━━━━━━━━━━━━━━━━━
💰 Preço: \$2.480,00
📈 24h: +1.8%
📉 7d: -0.5%
🔄 Volume: \$18.7B
🕐 $(date '+%H:%M:%S')"

echo "📤 Enviando ETH (carregando)..."
curl -sf -X POST "$BASE_URL/api/send" \
    -G \
    --data-urlencode "text=$MOCK_ETH_V1" \
    --data-urlencode "reference_key=eth-price" > /dev/null
echo "   OK"

echo "⏳ Simulando scraping (2s)..."
sleep 2

echo "✏️  Editando ETH com dados..."
curl -sf -X PUT "$BASE_URL/api/edit" \
    -G \
    --data-urlencode "reference_key=eth-price" \
    --data-urlencode "text=$MOCK_ETH_V2" > /dev/null
echo "   OK"
echo ""

echo "═══════════════════════════════════════"
echo "  ✅ Validação completa!"
echo "  Verifique o canal do Telegram."
echo "  Devem aparecer 2 mensagens editadas"
echo "  (BTC e ETH) com dados mockados."
echo "═══════════════════════════════════════"
