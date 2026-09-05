"""Chat da OLX via navegador com perfil persistente.

Login: na 1a execução abre o chat da OLX e espera você entrar na sua conta.
Depois a sessão fica salva no perfil.

⚠️ PRECISA CALIBRAR: diferente do WhatsApp, os seletores abaixo ainda NÃO foram
verificados contra o chat real da OLX. Abra o chat logado, use F12 para achar os
elementos e ajuste as constantes. Enquanto não estiverem certos, o canal apenas
avisa e devolve zero mensagens — nunca envia nada errado.
"""
import hashlib
import logging

from canais.base import Canal
from giro_client import MensagemEntrante

logger = logging.getLogger(__name__)

URL = "https://chat.olx.com.br/"

# --- Seletores (CALIBRAR contra o chat real) --------------------------------
SEL_LISTA_CONVERSAS = '[data-testid="conversation-list"]'
SEL_ITEM_CONVERSA   = '[data-testid="conversation-list"] li'
SEL_BADGE_NAO_LIDA  = '[data-testid="unread-badge"]'
SEL_TITULO_CONVERSA = '[data-testid="conversation-header-title"]'
SEL_MSG_RECEBIDA    = '[data-testid="message-received"]'
SEL_CAIXA_TEXTO     = 'textarea, [contenteditable="true"]'
SEL_BOTAO_ENVIAR    = '[data-testid="send-button"]'
# ---------------------------------------------------------------------------


class CanalOlx(Canal):
    nome = "olx"

    def __init__(self, navegador, max_conversas: int = 10):
        self.nav = navegador
        self.max_conversas = max_conversas
        self.pg = None
        self._vistos: set[str] = set()
        self._avisou_calibrar = False

    def iniciar(self) -> None:
        self.pg = self.nav.pagina(URL)
        logger.info("Aguardando o chat da OLX (faça login se for a 1a vez)…")
        try:
            self.pg.wait_for_selector(SEL_LISTA_CONVERSAS, timeout=180_000)
            logger.info("Chat da OLX conectado.")
        except Exception:
            logger.warning(
                "OLX: não achei a lista de conversas com '%s'. "
                "Calibre os seletores em canais/olx.py.", SEL_LISTA_CONVERSAS,
            )

    def _avisar_calibragem(self) -> None:
        if not self._avisou_calibrar:
            logger.warning(
                "OLX: seletores não bateram com a página — nenhuma mensagem lida. "
                "Ajuste as constantes SEL_* em canais/olx.py."
            )
            self._avisou_calibrar = True

    def ler_novas(self) -> list[MensagemEntrante]:
        if not self.pg:
            return []
        novas: list[MensagemEntrante] = []
        try:
            itens = self.pg.query_selector_all(SEL_ITEM_CONVERSA)[: self.max_conversas]
            if not itens:
                self._avisar_calibragem()
                return []
            for item in itens:
                if not item.query_selector(SEL_BADGE_NAO_LIDA):
                    continue
                item.click()
                self.pg.wait_for_timeout(900)
                cab = self.pg.query_selector(SEL_TITULO_CONVERSA)
                titulo = (cab.inner_text().strip() if cab else "") or "Conversa OLX"
                for bolha in self.pg.query_selector_all(SEL_MSG_RECEBIDA)[-5:]:
                    texto = (bolha.inner_text() or "").strip()
                    if not texto:
                        continue
                    msg_id = hashlib.sha1(f"{titulo}:{texto}".encode("utf-8")).hexdigest()[:20]
                    if msg_id in self._vistos:
                        continue
                    self._vistos.add(msg_id)
                    novas.append(MensagemEntrante(
                        canal=self.nome, thread_id=titulo, texto=texto,
                        msg_id=msg_id, contato_nome=titulo,
                    ))
        except Exception:
            logger.exception("OLX: falha ao ler conversas (seletor mudou?)")
        return novas

    def enviar(self, thread_id: str, texto: str) -> None:
        if not self.pg:
            raise RuntimeError("OLX não iniciada.")
        alvo = None
        for item in self.pg.query_selector_all(SEL_ITEM_CONVERSA):
            if thread_id.lower() in (item.inner_text() or "").lower():
                alvo = item
                break
        if not alvo:
            raise RuntimeError(f"Conversa '{thread_id}' não encontrada na OLX.")
        alvo.click()
        self.pg.wait_for_timeout(700)
        caixa = self.pg.wait_for_selector(SEL_CAIXA_TEXTO, timeout=15_000)
        caixa.click()
        caixa.type(texto, delay=15)
        botao = self.pg.query_selector(SEL_BOTAO_ENVIAR)
        if botao:
            botao.click()
        else:
            self.pg.keyboard.press("Enter")
        self.pg.wait_for_timeout(400)
        logger.info("OLX: resposta enviada para %s", thread_id)
