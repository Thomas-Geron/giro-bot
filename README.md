# Giro Bot

Leva as conversas do **WhatsApp do celular** para a Central de Mensagens do
**Giro**, e envia por ele as respostas que você escreve no painel.

Roda no **computador do lojista** (não no servidor): ele age dentro do navegador
já logado, com a sua sessão. Por isso não guarda senha de portal nenhum.

```
[Computador do lojista]                      [Giro na internet]
   Giro Bot  ──── mensagens que leu ────►  Central de Mensagens
             ◄─── respostas do painel ────
             ──── "enviei" (confirma) ───►
```

> Os canais com API oficial — **WhatsApp oficial** (Meta), **chat da OLX** e
> **Mercado Livre** — **não** passam pelo bot: funcionam direto no servidor do Giro,
> 24h por dia, mesmo com o computador desligado, e se ligam em **Minha loja**.
> O bot existe para um número que continua no aplicativo do celular.

---

## Para quem vai usar (sem terminal)

1. Instale o **GiroBot-Setup.exe** (duplo clique, avançar, concluir).
   Não pede senha de administrador.
2. Abra o **Giro Bot** pelo menu Iniciar ou pelo atalho da Área de Trabalho.
3. No Giro (site), vá em **Bot → Gerar token** e copie o token.
4. Na janela do Giro Bot: cole o **token**, marque os **canais** e clique em
   **Testar conexão**. Aparecendo o nome da sua loja, clique em **Iniciar**.
5. Na primeira vez com o WhatsApp, abre uma janela do navegador para você
   **ler o QR Code**. Depois disso ele lembra.

**Use um número só da loja.** O bot leva ao Giro as conversas individuais não
lidas; grupos, listas de transmissão, status e canais ficam de fora.

Deixe a janela aberta enquanto quiser receber e responder mensagens.

### Atualizações
O Giro Bot verifica sozinho, ao abrir, se existe versão nova. Havendo, ele
**pergunta** se você quer atualizar — se aceitar, baixa o instalador com barra
de progresso, fecha e instala. Nada é baixado sem você aceitar. Também dá para
checar na hora pelo botão **Buscar atualizações**.

**Requisitos:** Windows 10/11 com **Microsoft Edge** (já vem no Windows) ou
Google Chrome. Não precisa instalar Python nem nada além do instalador.

### Onde ficam os dados
`%APPDATA%\GiroBot` — configuração (`config.json`), sessão do navegador
(`perfil/`), o **registro** (`bot.log`, também no botão **Abrir registro**) e os
arquivos do canal de teste. Desinstalar **não** apaga essa pasta; apague à mão
se quiser zerar tudo.

---

## Testar sem mexer nos portais

Marque o canal **Simulado**. Escreva linhas em
`%APPDATA%\GiroBot\simulado_entrada.txt`:

```
5511999998888|Joao Silva|Esse carro ainda esta disponivel?
```

Elas viram conversas no Giro, no filtro **Teste do bot**. As respostas do painel
são gravadas em `simulado_saida.log`. Serve para validar a conexão antes de usar
o WhatsApp.

---

## Para desenvolver / gerar o instalador

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python gui.py          # a janela
python main.py         # modo terminal (usa o mesmo motor)
```

Gerar o executável e o instalador:

```bash
build.bat
```

- Gera `dist\GiroBot\GiroBot.exe` (aplicativo pronto, ~112 MB).
- Se o [Inno Setup 6](https://jrsoftware.org/isdl.php) estiver instalado, gera
  também `instalador\GiroBot-Setup.exe`.

Não embutimos navegador: o Playwright usa o **Edge/Chrome já instalado**
(`channel="msedge"`, com queda para `chrome` e por fim Chromium). Isso evita
baixar ~150 MB e simplifica o instalador.

### Estrutura

```
gui.py             janela do usuário (tkinter)
main.py            modo terminal
runner.py          motor: o ciclo entrada/saída, em thread própria
config.py          configuração em %APPDATA%\GiroBot\config.json
giro_client.py     ponte HTTP com o Giro
girobot.spec       receita do PyInstaller
installer.iss      receita do instalador (Inno Setup)
build.bat          gera exe + instalador
canais/
  base.py          interface Canal (iniciar / ler_novas / enviar)
  navegador.py     Playwright com perfil persistente (login salvo)
  simulado.py      canal de teste, sem navegador
  whatsapp.py      WhatsApp Web
checar_whatsapp.py confere o canal do WhatsApp contra uma página que imita o
                   WhatsApp Web (sem rede): python checar_whatsapp.py
```

Adicionar canal = criar uma classe que implementa `Canal` e registrá-la em
`canais/__init__.py`. O motor não muda.

### Publicar uma atualização (para o desenvolvedor)

A distribuição é por **GitHub Releases** — o mesmo canal que o app consulta.

```bash
# 1. suba o código
git add -A && git commit -m "novidades" && git push

# 2. crie a tag da versão
git tag v1.1.0
git push --tags
```

O workflow `.github/workflows/release.yml` cuida do resto no Windows do GitHub:
sincroniza `version.py` com a tag, gera o `.exe` (PyInstaller), instala o Inno
Setup, compila o `GiroBot-Setup.exe` e **publica a release** com ele anexado.

A partir daí:
- quem já tem o bot instalado recebe o aviso de atualização;
- a página **Bot** do Giro passa a oferecer o instalador novo (ela lê a mesma
  API de releases e mostra a versão).

> O repositório precisa se chamar como está em `version.py`
> (`GITHUB_OWNER` / `GITHUB_REPO`). Mudou de nome? Ajuste lá e em
> `app/routers/bot.py` no Giro.

### Contrato com o servidor (já implementado no Giro)

Autenticação: `Authorization: Bearer <token da loja>`.

| Método | Rota | Corpo / Resposta |
|---|---|---|
| `GET` | `/api/bot/ping` | → `{"ok": true, "loja": "Nome"}` |
| `POST` | `/api/bot/inbound` | ← `{"mensagens":[{canal, thread_id, texto, msg_id, contato_nome, titulo}]}` → `{"ok":true,"aceitas":N}` |
| `GET` | `/api/bot/outbound` | → `{"pendentes":[{id, canal, thread_id, texto}]}` |
| `POST` | `/api/bot/outbound/{id}/confirmar` | ← `{"ok":bool,"erro":"..."}` |

`msg_id` é o id estável da mensagem no canal — o servidor usa para não duplicar.

---

## Limitações (importante)

- **Só funciona com o computador ligado** e o programa aberto.
- **Automação de site é frágil**: se o WhatsApp Web muda o layout, os seletores
  precisam de ajuste (ficam no topo de `canais/whatsapp.py`). Quando o bot não
  consegue identificar de quem é uma conversa, ele a ignora e avisa no registro.
- **Ler marca como lida**: para ler, o bot abre a conversa, e o WhatsApp mostra
  os tracinhos azuis ao cliente mesmo antes de alguém responder.
- Automatizar o WhatsApp contraria os Termos de Uso dele e pode levar ao bloqueio
  do número. Para uso profissional, prefira o **WhatsApp oficial** do Giro.
