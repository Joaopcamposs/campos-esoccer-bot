# Como funciona

O bot é executado a cada 4 minutos.

- Scrap de quais são os confrontos nos próximos 10 minutos e resultados finalizados em: https://tipmanager.net/pt/sports/e-soccer/leagues/1/battle
- Scrap cacheado em: https://www.totalcorner.com/league/view/12995/end/Esoccer-Battle-8-mins-play
    - Estatisticas de jogadores
    - Estatisticas de gols e porcentagens over
- Gerar palpite sobre o jogo:
    - caso tenha mais de 20 jogos de amostragem do jogador, use os dados consolidados nesse range
    - caso tenha menos de 20 jogos de amostragem do jogador, use os dados consolidados externos no range completo
- Enviar palpite e salvar no banco junto ao id da mensagem retornado
- Atualizar palpites de mensagens anteriores de acordo com o resultado finalizado.
- Atualizar palpite salvo como editado/concluido e o resultado. Salvar gols ocorridos e uma flag de sucesso ou erro.
- Sempre evite deduplicação de palpites

Precisamos de uma tabela local de estatisticas dos jogadores. Assim que um resultado for finalizado, atualizar a tabela local com as estatisticas do jogador.
Cruze o maximo de dados possiveis para gerar um palpite assertivo

Formato da mensagem de palpite:
```
"E-soccer Battle 8 minutos - LIVE @1.5+\n\n"
f"🎯 {upcoming_match.home_player} ({upcoming_match.home_team}) vs "
f"{upcoming_match.away_player} ({upcoming_match.away_team})\n"
f"⚽️ Gols esperado: {expected_total_goals:.2f}\n"
f"🥅 Over {line} gols\n"
f"🕒 {_format_brt_time(upcoming_match.starts_at)}\n\n"
"📝 Análise:\n"
f"{reasons}"
```

```
reasons: 
👨🏻 *Jogador 1*: AVG [GF: xx | GA: xx]
🧔🏻 *Jogador 2*: AVG [GF: xx | GA: xx]
Frequencia de gols acima de xx
```

apos editar mensagem, adicionar no final:
```
f"/n/n ✅ ou ❌"
```
