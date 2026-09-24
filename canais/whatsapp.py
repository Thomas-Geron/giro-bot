"""WhatsApp Web via navegador com perfil persistente.

Login: na 1a execução abre o WhatsApp Web e espera você ler o QR code. Depois
a sessão fica salva no perfil e não pede mais.

A cada ciclo:
- procura conversas com o aviso de "não lida" na lista;
- abre cada uma, lê as mensagens novas (quantas o aviso indicar) e FECHA a
  conversa (Esc), para que a próxima mensagem dela volte a acender o aviso;
- só aceita conversa individual. Grupo, lista de transmissão, status e canal
  ficam de fora — e são lembrados, para não serem abertos de novo.

Abrir a conversa faz o WhatsApp marcar como lida (o cliente vê os tracinhos
azuis). Não há como ler pelo WhatsApp Web sem abrir.

⚠️ SELETORES: o WhatsApp Web muda o DOM com frequência. Ficam isolados nas
constantes abaixo. Se o bot não conseguir identificar de quem é a conversa, ele
PULA essa conversa e avisa no registro — nunca manda ao Giro algo sem saber a origem.
"""
import logging
import re

from canais.base import Canal
from giro_client import MensagemEntrante

logger = logging.getLogger(__name__)

URL = "https://web.whatsapp.com/"

# --- Seletores (ajustáveis) -------------------------------------------------
SEL_LISTA_CONVERSAS = '#pane-side'
SEL_ITENS_CONVERSA  = ('#pane-side [role="listitem"]', '#pane-side [role="row"]')  # o 2o, se o 1o sumir
SEL_BADGE_NAO_LIDA  = '[aria-label*="não lida" i], [aria-label*="unread" i]'
SEL_TITULO_CONVERSA = '#main header [title]'
SEL_MSG_RECEBIDA    = '#main div.message-in'
SEL_CAIXA_TEXTO     = '#main footer div[contenteditable="true"], footer div[contenteditable="true"]'
# ---------------------------------------------------------------------------

MAX_POR_CONVERSA = 20
SEM_TEXTO = "[Mensagem sem texto: foto, áudio, figurinha ou documento. Veja no WhatsApp.]"

# O WhatsApp Web marca cada bolha com data-id = "<de mim?>_<conversa>_<id>[_<quem, em grupo>]".
_JS_BOLHA = """e => {
    const alvo = e.closest('[data-id]') || e.querySelector('[data-id]');
    const textos = e.querySelectorAll('span.selectable-text');
    let texto = '';
    if (textos.length) {                       // o último é o corpo (antes dele vem a citação)
        const copia = textos[textos.length - 1].cloneNode(true);
        copia.querySelectorAll('img[alt]').forEach(i => i.replaceWith(i.alt));  // emojis
        copia.querySelectorAll('br').forEach(b => b.replaceWith('\\n'));
        texto = copia.textContent || '';
    }
    return [alvo ? alvo.getAttribute('data-id') : '', texto.trim()];
}"""


def ler_data_id(data_id: str) -> tuple[str, str] | None:
    """'false_5521999999999@c.us_3EB0' -> ('5521999999999@c.us', data_id).
    None quando não é conversa individual (grupo, transmissão, status, canal) ou
    quando o formato não é o esperado."""
    partes = (data_id or "").split("_")
    if len(partes) < 3 or partes[0] not in ("true", "false"):
        return None
    conversa = partes[1]
    if not conversa.endswith(("@c.us", "@lid", "@s.whatsapp.net")):
        return None
    return conversa, data_id


class CanalWhatsApp(Canal):
    nome = "whatsapp"

    def __init__(self, navegador, max_conversas: int = 10):
        self.nav = navegador
        self.max_conversas = max_conversas
        self.pg = None
        self._vistos: set[str] = set()
        self._pular: set[str] = set()   # títulos de grupos e conversas que não deu para identificar
        self._avisou_sem_id = False

    def iniciar(self) -> None:
        self.pg = self.nav.pagina(URL)
        logger.info("Aguardando o WhatsApp Web carregar (leia o QR se for a 1a vez)…")
        self.pg.wait_for_selector(SEL_LISTA_CONVERSAS, timeout=180_000)
        logger.info("WhatsApp Web conectado.")

    # ── leitura ───────────────────────────────────────────────────────────
    def _itens(self) -> list:
        for seletor in SEL_ITENS_CONVERSA:
            itens = self.pg.query_selector_all(seletor)
            if itens:
                return itens
        return []

    @staticmethod
    def _titulos(item) -> list[str]:
        return item.evaluate("e => [...e.querySelectorAll('[title]')].map(x => x.getAttribute('title'))")

    @staticmethod
    def _quantidade(badge) -> int:
        """Quantas mensagens novas o aviso indica (sem número = pelo menos 1)."""
        achado = re.search(r"\d+", (badge.inner_text() or "") + " " + (badge.get_attribute("aria-label") or ""))
        return min(int(achado.group()), MAX_POR_CONVERSA) if achado else 1

    def _fechar_conversa(self) -> None:
        self.pg.keyboard.press("Escape")
        self.pg.wait_for_timeout(300)

    def ler_novas(self) -> list[MensagemEntrante]:
        if not self.pg:
            return []
        novas: list[MensagemEntrante] = []
        try:
            for item in self._itens()[: self.max_conversas]:
                badge = item.query_selector(SEL_BADGE_NAO_LIDA)
                if not badge or set(self._titulos(item)) & self._pular:
                    continue
                quantas = self._quantidade(badge)
                item.click()
                self.pg.wait_for_timeout(800)
                cab = self.pg.query_selector(SEL_TITULO_CONVERSA)
                titulo = (cab.get_attribute("title") if cab else "") or "Contato"
                novas += self._ler_conversa(titulo, quantas)
                self._fechar_conversa()
        except Exception:
            logger.exception("WhatsApp: falha ao ler conversas (o WhatsApp Web mudou?)")
        return novas

    def _ler_conversa(self, titulo: str, quantas: int) -> list[MensagemEntrante]:
        lidas = []
        for bolha in self.pg.query_selector_all(SEL_MSG_RECEBIDA)[-quantas:]:
            data_id, texto = bolha.evaluate(_JS_BOLHA)
            origem = ler_data_id(data_id)
            if origem is None:
                self._pular.add(titulo)
                if not data_id and not self._avisou_sem_id:
                    self._avisou_sem_id = True
                    logger.warning("WhatsApp: não consegui identificar de quem é a conversa "
                                   "(o WhatsApp Web pode ter mudado). Ela foi ignorada.")
                return []  # grupo, transmissão ou conversa sem identificação: nada vai ao Giro
            conversa, msg_id = origem
            if msg_id in self._vistos:
                continue
            self._vistos.add(msg_id)
            lidas.append(MensagemEntrante(
                canal=self.nome, thread_id=conversa, texto=texto or SEM_TEXTO,
                msg_id=msg_id, contato_nome=titulo,
            ))
        return lidas

    # ── envio ─────────────────────────────────────────────────────────────
    def _abrir_pela_lista(self, nome: str) -> bool:
        if not nome:
            return False
        for item in self._itens():
            if nome in self._titulos(item):
                item.click()
                self.pg.wait_for_timeout(600)
                return True
        return False

    def enviar(self, thread_id: str, texto: str, contato_nome: str = "") -> None:
        if not self.pg:
            raise RuntimeError("WhatsApp não iniciado.")
        if not self._abrir_pela_lista(contato_nome):
            numero = thread_id.split("@")[0] if thread_id.endswith("@c.us") else ""
            if not numero.isdigit():
                raise RuntimeError(f"Conversa com '{contato_nome or 'o contato'}' não encontrada na lista do WhatsApp.")
            # Link de conversa do próprio WhatsApp: abre pelo número mesmo fora da lista (recarrega a página)
            self.pg.goto(f"{URL}send?phone={numero}", wait_until="domcontentloaded")
        caixa = self.pg.wait_for_selector(SEL_CAIXA_TEXTO, timeout=60_000)
        caixa.click()
        for i, linha in enumerate(texto.split("\n")):
            if i:
                self.pg.keyboard.press("Shift+Enter")  # Enter sozinho mandaria a mensagem pela metade
            if linha:
                self.pg.keyboard.type(linha, delay=15)
        self.pg.keyboard.press("Enter")
        self.pg.wait_for_timeout(600)
        self._fechar_conversa()
        logger.info("WhatsApp: resposta enviada.")
