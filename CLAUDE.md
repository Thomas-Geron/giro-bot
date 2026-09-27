# Giro Bot — regras

## Licença: só funciona com o plano certo e o pagamento em dia

Vale para este bot e para **todo bot novo do Giro**:

- Ao iniciar, o bot consulta o Giro: `GET /api/bot/licenca?bot=giro_bot` com
  `Authorization: Bearer <token da loja>` (`GiroClient.licenca`). O Giro confere
  o plano (o Giro Bot faz parte dos planos Loja e Revenda), o pagamento e o
  termo de riscos.
- **Sem conseguir conferir (sem internet, Giro fora do ar) o bot não inicia.**
  Não existe licença guardada no computador.
- Qualquer resposta 403 com `motivo` (`plano` | `pagamento`) ou `termo` vira
  `BotBloqueado`: o bot não inicia ou, se já estiver rodando, para na hora e
  mostra a mensagem do Giro com o botão para abrir Meu plano.
- Enquanto roda, toda chamada ao Giro (inbound/outbound) passa pela mesma
  checagem no servidor — pagamento que vence com o bot aberto derruba o bot.
- O instalador é público no GitHub; a trava de verdade é essa consulta.
- A regra e a lista de planos ficam no site: `revendedora-web/app/services/planos.py`
  e `revendedora-web/CLAUDE.md`.

`python checar_licenca.py` confere tudo isso sem rede.

## Outros

- Visual: `ui_*.py` são cópias do MarketplaceBot (mudar lá e cá).
- Termo de riscos obrigatório antes de iniciar (`checar_termo.py`).
- Publicar: subir `version.py`, commit, `git tag vX.Y.Z` e push da tag pela conta
  Thomas-Geron (`gh auth switch --user Thomas-Geron`, depois voltar para RakannaraK).
