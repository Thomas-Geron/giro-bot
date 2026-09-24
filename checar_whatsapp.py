"""Confere o canal do WhatsApp contra uma página que imita o WhatsApp Web.

Não usa o WhatsApp de verdade (nem a rede): serve para mudar canais/whatsapp.py
sem medo. Rodar:  python checar_whatsapp.py
Se o WhatsApp Web real mudar, o que quebra são os seletores — isto aqui não pega.
"""
import logging
import sys
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright

from canais.whatsapp import SEM_TEXTO, CanalWhatsApp, URL

PAGINA = """<!doctype html><html><body>
<div id="side"><div id="pane-side"><div role="grid">
  <div role="listitem" data-c="ana"><span title="Cliente Ana">Cliente Ana</span><span aria-label="2 mensagens não lidas">2</span></div>
  <div role="listitem" data-c="familia"><span title="Família">Família</span><span aria-label="5 mensagens não lidas">5</span></div>
  <div role="listitem" data-c="estranho"><span title="Estranho">Estranho</span><span aria-label="1 mensagem não lida">1</span></div>
  <div role="listitem" data-c="quieto"><span title="Sem novidade">Sem novidade</span></div>
</div></div></div>
<div id="main"></div>
<script>
window.__enviados = []; window.__fechou = 0; window.__abertas = [];
const CONVERSAS = {
  ana: {titulo: 'Cliente Ana', manter: false, msgs: [
    ['false_5521988887777@c.us_ANTIGA', 'mensagem antiga, já lida'],
    ['false_5521988887777@c.us_M1', 'Oi! Ainda tem o <img alt="🚗" class="emoji"> Tracker?<br>Aceita troca?'],
    ['false_5521988887777@c.us_M2', null]]},
  familia: {titulo: 'Família', manter: true, msgs: [
    ['false_120363000000@g.us_G1_5521977776666@c.us', 'bom dia grupo']]},
  estranho: {titulo: 'Estranho', manter: true, msgs: [[null, 'sem identificação']]},
  novo: {titulo: '+55 21 95555-4444', manter: false, msgs: []},
};
function abrir(chave) {
  const c = CONVERSAS[chave];
  window.__abertas.push(chave);
  let html = '<header><span title="' + c.titulo + '">' + c.titulo + '</span></header><div class="msgs">';
  for (const [id, texto] of c.msgs) {
    const corpo = texto === null ? '<img src="foto.jpg">'
      : '<div class="copyable-text"><span class="selectable-text"><span>' + texto + '</span></span></div>';
    html += (id ? '<div data-id="' + id + '">' : '<div>') + '<div class="message-in">' + corpo + '</div></div>';
  }
  html += '</div><footer><div contenteditable="true" id="caixa"></div></footer>';
  document.getElementById('main').innerHTML = html;
  if (!c.manter) {
    const item = document.querySelector('[data-c="' + chave + '"] [aria-label]');
    if (item) item.remove();   // abriu: o WhatsApp tira o aviso de não lida
  }
}
document.querySelectorAll('[role=listitem]').forEach(i => i.addEventListener('click', () => abrir(i.dataset.c)));
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { document.getElementById('main').innerHTML = ''; window.__fechou++; return; }
  if (e.key === 'Enter' && e.target.id === 'caixa') {
    e.preventDefault();
    if (e.shiftKey) { document.execCommand('insertText', false, '\\n'); return; }  // quebra onde está o cursor
    window.__enviados.push(e.target.innerText.replace(/\\n$/, '')); e.target.textContent = '';
  }
});
const telefone = new URLSearchParams(location.search).get('phone');
if (telefone) abrir('novo');
</script></body></html>"""

falhas = []


def checar(cond, msg):
    print(("  OK   " if cond else "  FALHA ") + msg)
    if not cond:
        falhas.append(msg)


class NavegadorFalso:
    def __init__(self, pg):
        self.pg = pg

    def pagina(self, url):
        self.pg.goto(url)
        return self.pg


class Avisos(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.textos = []

    def emit(self, registro):
        self.textos.append(registro.getMessage())


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    avisos = Avisos()
    logging.getLogger("canais.whatsapp").addHandler(avisos)
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="msedge", headless=True)
        pg = nav.new_page()
        abertos = []
        def servir(route):
            abertos.append(route.request.url)
            route.fulfill(status=200, content_type="text/html; charset=utf-8", body=PAGINA)
        pg.route("https://web.whatsapp.com/**", servir)
        canal = CanalWhatsApp(NavegadorFalso(pg))
        canal.iniciar()

        print("[lendo]")
        novas = canal.ler_novas()
        checar(len(novas) == 2, f"lê só as 2 mensagens novas da Ana ({len(novas)})")
        if len(novas) == 2:
            primeira, segunda = novas
            checar(primeira.thread_id == "5521988887777@c.us" and primeira.contato_nome == "Cliente Ana",
                   f"conversa identificada pelo número, com o nome do contato ({primeira.thread_id})")
            checar(primeira.texto == "Oi! Ainda tem o 🚗 Tracker?\nAceita troca?",
                   f"texto com emoji e quebra de linha ({primeira.texto!r})")
            checar(segunda.texto == SEM_TEXTO, "foto sem legenda vira aviso, não some")
            checar(primeira.msg_id != segunda.msg_id, "cada mensagem com id próprio (não se confundem)")
        checar(not any(m.contato_nome == "Família" for m in novas), "grupo fica de fora")
        checar(not any(m.contato_nome == "Estranho" for m in novas), "conversa sem identificação fica de fora")
        checar(any("não consegui identificar" in t for t in avisos.textos), "e isso fica avisado no registro")
        checar(pg.evaluate("window.__fechou") == 3, f"fecha cada conversa depois de ler ({pg.evaluate('window.__fechou')})")

        print("[segunda volta]")
        antes = len(pg.evaluate("window.__abertas"))
        checar(canal.ler_novas() == [], "nada repetido")
        checar(len(pg.evaluate("window.__abertas")) == antes, "grupo e conversa estranha não são abertos de novo")

        print("[respondendo]")
        canal.enviar("5521988887777@c.us", "Tem sim!\nPode vir ver amanhã.", "Cliente Ana")
        checar(pg.evaluate("window.__enviados") == ["Tem sim!\nPode vir ver amanhã."],
               f"resposta de várias linhas sai numa mensagem só ({pg.evaluate('window.__enviados')})")
        checar(pg.evaluate("window.__abertas").count("ana") == 2, "achou a Ana pela lista")
        checar(pg.evaluate("document.getElementById('main').innerHTML") == "", "fecha a conversa depois de enviar")

        canal.enviar("5521955554444@c.us", "Olá!", "Novo Cliente")
        telefone = parse_qs(urlsplit(abertos[-1]).query).get("phone", [""])[0]
        checar(telefone == "5521955554444", f"fora da lista, abre pelo número ({abertos[-1]})")
        checar(pg.evaluate("window.__enviados")[-1] == "Olá!", "e envia")

        try:
            canal.enviar("98765432109876@lid", "Oi", "Sem Número")
            checar(False, "conversa sem número e fora da lista deveria dar erro")
        except RuntimeError as exc:
            checar("não encontrada" in str(exc), f"sem número e fora da lista: erro claro ({exc})")
        nav.close()

    print("\nRESULTADO:", "TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)")
    for f in falhas:
        print(" -", f)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
