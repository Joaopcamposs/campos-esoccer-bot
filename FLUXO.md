# Como funciona

O bot é executado a cada 4 minutos.

- Consultar quais são os confrontos nos próximos 5 minutos em: https://www.aceodds.com/pt/bet365-transmissao-ao-vivo/futebol/e-soccer-battle-8-minutos-de-jogo.html
- Caso ja tenha dados suficientes, considerar ultimas 20 partidas do jogador para gerar palpite
- Caso a execucao mostre banco de dados vazio, deve-se extrair resultados consolidados em: https://www.totalcorner.com/league/view/12995/end/Esoccer-Battle-8-mins-play, pois há uma tabela de Player Statistics das ultimas 48h. Esses dados devem ser salvos no banco em uma tabela alternativa de consolidados externos.
- Gerar palpite e salvar dados no banco (para comparacao com resultados posteriormente)
- Consultar resultados dos confrontos dos ultimos 5 minutos em: https://esoccerbet.com.br/fifa-8-minutos/ e salvar no banco.
- Atualizar mensagem do bot com os palpites gerados.
- Enviar os palpites para o bot

Devemos evitar fallbacks com resultados falsos.
A prioridade é consultar a tabela com dados reais que vão ser extraidos ao longo do tempo.
Caso essa tabela esteja vazia ou abaixo de 20, use a tabela de consolidados extraidos externamente.
Sempre salve resultados consultado para alimentar a tabela. Sempre salve palpites gerados.
Ignore odds por enquanto. Nosso foco será operar em live buscando o palpite de gols, com odds acima de 1.5.
