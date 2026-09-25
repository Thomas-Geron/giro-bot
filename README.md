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

### Termo de riscos (obrigatório)
O bot não é oficial, e usar automação no WhatsApp contraria os Termos de Serviço
dele (o número pode ser bloqueado). Por isso o uso depende de aceitar o **termo de
riscos**, em três pontos:

1. **No instalador**: a página de licença só deixa seguir com "Eu aceito".
2. **No site do Giro**, página **Bot**: a conta da loja marca cada declaração e
   digita o nome completo. Sem esse aceite, download e token nem aparecem, e o
   Giro recusa o bot.
3. **No aplicativo**: antes de iniciar pela primeira vez (e sempre que o termo
   mudar), a janela mostra o termo e pede o mesmo aceite.

Os riscos ficam **sempre à vista**: no topo da janela do bot, na página Bot do
Giro e em cada conversa trazida pelo bot.

Deixe a janela aberta enquanto quiser receber e responder mensagens.

### Atualizações
O Giro Bot verifica sozinho se existe versão nova: ao abrir e, com a janela
aberta, de 6 em 6 horas. Havendo, aparece um aviso azul no topo com
**Atualizar agora** (ao abrir, ele também já pergunta). Se aceitar, baixa o
instalador com barra de progresso, fecha e instala. Nada é baixado sem você
aceitar. Também dá para checar na hora pelo botão **Buscar atualizações**.
A consulta usa a página de releases do GitHub, não a API (que sem login só
aceita 60 consultas por hora por conexão).

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
ui_*.py           visual (tema, cartões, interruptor, registro, animação):
                   cópia do MarketplaceBot, com as cores do Giro — mudar lá e cá
assets/            ícone do app e a marca da lateral (logo_<lado>.png), da marca do site
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
termo.py           títulos dos riscos (aviso sem internet) e regra do nome
TERMO.txt          termo para a página de licença do instalador
checar_whatsapp.py confere o canal do WhatsApp contra uma página que imita o
                   WhatsApp Web (sem rede): python checar_whatsapp.py
checar_termo.py    confere a janela do termo (sem rede): python checar_termo.py
checar_atualizacao.py  confere o aviso de versão nova (sem rede)
```

Adicionar canal = criar uma classe que implementa `Canal` e registrá-la em
`canais/__init__.py`. O motor não muda.

### O termo mudou?
O texto oficial fica no Giro (`app/services/termo_bot.py`). Ao mudar, suba a
`VERSAO` lá — todo mundo precisa aceitar de novo — e regere o `TERMO.txt` daqui:

```bash
curl -s https://revendedora-web.onrender.com/api/bot/termo.txt -o TERMO.txt
```
(salve como UTF-8 com BOM, que é como o Inno Setup lê acentos) e publique uma versão.

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
