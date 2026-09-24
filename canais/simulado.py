"""Canal simulado — para testar a ponte com o Giro sem abrir navegador.

Entrada: cada linha de `simulado_entrada.txt` vira uma mensagem recebida, no
formato  thread_id|nome do contato|texto
Saída:   as respostas são gravadas em `simulado_saida.log`.
"""
import hashlib
import logging
from pathlib import Path

from canais.base import Canal
from giro_client import MensagemEntrante

logger = logging.getLogger(__name__)

import config

ARQ_ENTRADA = config.CONFIG_DIR / "simulado_entrada.txt"
ARQ_SAIDA = config.CONFIG_DIR / "simulado_saida.log"


class CanalSimulado(Canal):
    nome = "simulado"

    def __init__(self):
        self._vistos: set[str] = set()

    def iniciar(self) -> None:
        config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        ARQ_ENTRADA.touch(exist_ok=True)
        logger.info("Canal simulado pronto. Escreva linhas em %s", ARQ_ENTRADA)

    def ler_novas(self) -> list[MensagemEntrante]:
        novas = []
        for linha in ARQ_ENTRADA.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            partes = linha.split("|", 2)
            if len(partes) < 3:
                continue
            thread_id, nome, texto = (p.strip() for p in partes)
            msg_id = hashlib.sha1(linha.encode("utf-8")).hexdigest()[:16]
            if msg_id in self._vistos:
                continue
            self._vistos.add(msg_id)
            novas.append(MensagemEntrante(
                canal=self.nome, thread_id=thread_id, texto=texto,
                msg_id=msg_id, contato_nome=nome,
            ))
        return novas

    def enviar(self, thread_id: str, texto: str, contato_nome: str = "") -> None:
        with ARQ_SAIDA.open("a", encoding="utf-8") as f:
            f.write(f"[{thread_id}] {texto}\n")
        logger.info("Resposta simulada gravada em %s", ARQ_SAIDA.name)
