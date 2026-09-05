"""WhatsApp Web via navegador com perfil persistente.

Login: na 1a execução abre o WhatsApp Web e espera você ler o QR code. Depois
a sessão fica salva no perfil e não pede mais.

⚠️ SELETORES: o WhatsApp Web muda o DOM com frequência. Todos os seletores
estão isolados nas constantes abaixo — se algo parar de funcionar, ajuste aqui
(F12 no WhatsApp Web) sem mexer no resto do bot.
"""
import hashlib
import logging

from canais.base import Canal
from giro_client import MensagemEntrante

logger = logging.getLogger(__name__)

URL = "https://web.whatsapp.com/"

# --- Seletores (ajustáveis) -------------------------------------------------
SEL_LISTA_CONVERSAS = '#pane-side'
SEL_ITEM_CONVERSA   = '#pane-side [role="listitem"]'
SEL_BADGE_NAO_LIDA  = '[aria-label*="não lida"], [aria-label*="mensagem não lida"]'
SEL_TITULO_CONVERSA = 'header [title]'
SEL_MSG_RECEBIDA    = 'div.message-in'
SEL_TEXTO_MSG       = 'span.selectable-text span'
SEL_CAIXA_TEXTO     = 'footer div[contenteditable="true"]'
# ---------------------------------------------------------------------------


class CanalWhatsApp(Canal):
    nome = "whatsapp"

    def __init__(self, navegador, max_conversas: int = 10):
        self.nav = navegador
        self.max_conversas = max_conversas
        self.pg = None
        self._vistos: set[str] = set()

    def iniciar(self) -> None:
        self.pg = self.nav.pagina(URL)
        logger.info("Aguardando o WhatsApp Web carregar (leia o QR se for a 1a vez)…")
        self.pg.wait_for_selector(SEL_LISTA_CONVERSAS, timeout=180_000)
        logger.info("WhatsApp Web conectado.")

    def _abrir_conversa(self, item) -> str:
        item.click()
        self.pg.wait_for_timeout(800)
        cab = self.pg.query_selector(SEL_TITULO_CONVERSA)
        return (cab.get_attribute("title") if cab else "") or "desconhecido"

    def ler_novas(self) -> list[MensagemEntrante]:
        if not self.pg:
            return []
        novas: list[MensagemEntrante] = []
        try:
            itens = self.pg.query_selector_all(SEL_ITEM_CONVERSA)[: self.max_conversas]
            for item in itens:
                if not item.query_selector(SEL_BADGE_NAO_LIDA):
                    continue  # sem mensagem nova
                titulo = self._abrir_conversa(item)
                for bolha in self.pg.query_selector_all(SEL_MSG_RECEBIDA)[-5:]:
                    texto_el = bolha.query_selector(SEL_TEXTO_MSG)
                    texto = (texto_el.inner_text() if texto_el else "").strip()
                    if not texto:
                        continue
                    bruto = bolha.get_attribute("data-id") or f"{titulo}:{texto}"
                    msg_id = hashlib.sha1(bruto.encode("utf-8")).hexdigest()[:20]
                    if msg_id in self._vistos:
                        continue
                    self._vistos.add(msg_id)
                    novas.append(MensagemEntrante(
                        canal=self.nome, thread_id=titulo, texto=texto,
                        msg_id=msg_id, contato_nome=titulo,
                    ))
        except Exception:
            logger.exception("WhatsApp: falha ao ler conversas (seletor mudou?)")
        return novas

    def enviar(self, thread_id: str, texto: str) -> None:
        if not self.pg:
            raise RuntimeError("WhatsApp não iniciado.")
        # Localiza a conversa pelo título exato e envia
        item = self.pg.query_selector(f'{SEL_ITEM_CONVERSA} span[title="{thread_id}"]')
        if not item:
            raise RuntimeError(f"Conversa '{thread_id}' não encontrada na lista.")
        item.click()
        self.pg.wait_for_timeout(600)
        caixa = self.pg.wait_for_selector(SEL_CAIXA_TEXTO, timeout=15_000)
        caixa.click()
        caixa.type(texto, delay=15)
        self.pg.keyboard.press("Enter")
        self.pg.wait_for_timeout(400)
        logger.info("WhatsApp: resposta enviada para %s", thread_id)
