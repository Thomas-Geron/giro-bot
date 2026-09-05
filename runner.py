"""Motor do bot: o ciclo entrada/saída, isolado da interface.

Roda numa thread própria (o Playwright precisa ser criado e usado na MESMA
thread, por isso o navegador nasce aqui dentro, nunca na thread da janela).
"""
import logging
import threading
import time
from typing import Callable, Optional

import config
from canais import criar_canais
from giro_client import GiroClient

logger = logging.getLogger(__name__)


class Runner:
    def __init__(self, cfg: dict, log: Optional[Callable[[str], None]] = None):
        self.cfg = cfg
        self._log = log or (lambda msg: logger.info(msg))
        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.loja: str = ""

    # ── controle ──────────────────────────────────────────────────────────
    @property
    def rodando(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def iniciar(self) -> None:
        if self.rodando:
            return
        self._parar.clear()
        self._thread = threading.Thread(target=self._executar, daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()

    def aguardar(self, timeout: float = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    # ── testes rápidos ────────────────────────────────────────────────────
    def testar_conexao(self) -> dict:
        cli = GiroClient(self.cfg.get("giro_url", ""), self.cfg.get("token", ""))
        try:
            return cli.ping()
        finally:
            cli.fechar()

    # ── ciclo ─────────────────────────────────────────────────────────────
    def _ciclo(self, cli: GiroClient, canais: dict) -> None:
        for nome, canal in canais.items():
            try:
                novas = canal.ler_novas()
            except Exception as exc:
                self._log(f"[{nome}] erro ao ler mensagens: {exc}")
                continue
            if not novas:
                continue
            res = cli.enviar_inbound(novas)
            if "erro" in res:
                self._log(f"[{nome}] o Giro recusou {len(novas)} mensagem(ns): {res['erro']}")
            else:
                self._log(f"[{nome}] {len(novas)} mensagem(ns) enviada(s) ao Giro")

        for pendente in cli.buscar_outbound():
            nome = pendente.get("canal")
            canal = canais.get(nome)
            envio_id = pendente.get("id")
            if not canal:
                cli.confirmar(envio_id, False, f"Canal '{nome}' não está ativo neste computador.")
                continue
            try:
                canal.enviar(pendente.get("thread_id", ""), pendente.get("texto", ""))
                cli.confirmar(envio_id, True)
                self._log(f"[{nome}] resposta enviada")
            except Exception as exc:
                self._log(f"[{nome}] falha ao enviar resposta: {exc}")
                cli.confirmar(envio_id, False, str(exc))

    def _executar(self) -> None:
        cli = GiroClient(self.cfg.get("giro_url", ""), self.cfg.get("token", ""))
        canais, navegador = {}, None
        try:
            pong = cli.ping()
            if "erro" in pong:
                self._log(f"Não consegui falar com o Giro: {pong['erro']}")
                self._log("Confira o endereço e o token, depois tente de novo.")
                return
            self.loja = pong.get("loja") or "loja"
            self._log(f"Conectado ao Giro como: {self.loja}")

            canais, navegador = criar_canais(
                self.cfg.get("canais", []), headless=bool(self.cfg.get("headless")),
            )
            if not canais:
                self._log("Nenhum canal válido selecionado.")
                return

            for nome, canal in canais.items():
                try:
                    canal.iniciar()
                    self._log(f"[{nome}] pronto")
                except Exception as exc:
                    self._log(f"[{nome}] falha ao iniciar: {exc}")

            self._log("Bot rodando. Deixe esta janela aberta.")
            intervalo = max(5, int(self.cfg.get("poll_segundos") or 15))
            while not self._parar.is_set():
                try:
                    self._ciclo(cli, canais)
                except Exception as exc:
                    self._log(f"Erro no ciclo: {exc}")
                for _ in range(intervalo):
                    if self._parar.is_set():
                        break
                    time.sleep(1)
        except Exception as exc:
            self._log(f"Erro inesperado: {exc}")
        finally:
            for canal in canais.values():
                try:
                    canal.encerrar()
                except Exception:
                    pass
            if navegador:
                try:
                    navegador.fechar()
                except Exception:
                    pass
            cli.fechar()
            self._log("Bot parado.")
