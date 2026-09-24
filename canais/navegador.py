"""Navegador Playwright com perfil persistente.

Perfil persistente = o login (QR do WhatsApp) fica salvo em
disco e sobrevive entre execuções: o lojista loga uma vez só.
"""
import logging
from pathlib import Path

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


class Navegador:
    def __init__(self, perfil_dir: Path, headless: bool = False):
        self.perfil_dir = Path(perfil_dir)
        self.headless = headless
        self._pw = None
        self.contexto = None

    def abrir(self):
        """Usa o Edge/Chrome já instalado; só cai no Chromium do Playwright
        se nenhum dos dois existir (assim o instalador não precisa baixar
        ~150 MB de navegador)."""
        self.perfil_dir.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        comuns = dict(
            user_data_dir=str(self.perfil_dir),
            headless=self.headless,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        ultimo_erro = None
        for canal in ("msedge", "chrome", None):
            try:
                if canal:
                    self.contexto = self._pw.chromium.launch_persistent_context(channel=canal, **comuns)
                else:
                    self.contexto = self._pw.chromium.launch_persistent_context(**comuns)
                logger.info("Navegador aberto (%s, perfil: %s)", canal or "chromium", self.perfil_dir)
                return self.contexto
            except Exception as exc:
                ultimo_erro = exc
        raise RuntimeError(
            "Não consegui abrir o navegador. Instale o Microsoft Edge ou o Google Chrome. "
            f"Detalhe: {ultimo_erro}"
        )

    def pagina(self, url: str):
        """Reaproveita uma aba já aberta na mesma origem, ou abre uma nova."""
        origem = url.split("/")[2] if "//" in url else url
        for p in self.contexto.pages:
            if origem in (p.url or ""):
                return p
        pg = self.contexto.new_page()
        pg.goto(url, wait_until="domcontentloaded")
        return pg

    def fechar(self):
        try:
            if self.contexto:
                self.contexto.close()
        finally:
            if self._pw:
                self._pw.stop()
