"""Ponte HTTP com o Giro.

O bot é o "braço" na máquina do lojista; o Giro é o cérebro (banco + telas).
Contrato (lado servidor, prefixo /api/bot, autenticado por Bearer token da loja):

  GET  /api/bot/ping                    -> {"ok": true, "loja": "..."}
  POST /api/bot/inbound                 <- {"mensagens": [MensagemEntrante, ...]}
                                        -> {"ok": true, "aceitas": N}
  GET  /api/bot/outbound                -> {"pendentes": [{id, canal, thread_id, texto}]}
  POST /api/bot/outbound/{id}/confirmar <- {"ok": bool, "erro": "..."}
"""
import logging
from dataclasses import asdict, dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class MensagemEntrante:
    canal: str            # 'whatsapp' | 'simulado'
    thread_id: str        # id da conversa no canal (ex.: telefone, id do chat)
    texto: str
    msg_id: str           # id único da mensagem no canal (idempotência)
    contato_nome: str = ""
    titulo: str = ""      # assunto/anúncio, quando o canal expõe
    enviada_em: str = ""  # ISO-8601, se o canal informar


class GiroClient:
    def __init__(self, url: str, token: str, timeout: float = 20.0):
        self.url = (url or "").rstrip("/")
        self.token = token or ""
        self._http = httpx.Client(
            timeout=timeout,
            headers={"Authorization": f"Bearer {self.token}"},
        )

    def fechar(self) -> None:
        self._http.close()

    def ping(self) -> dict:
        try:
            r = self._http.get(f"{self.url}/api/bot/ping")
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            return {"erro": f"HTTP {exc.response.status_code}"}
        except Exception as exc:
            return {"erro": str(exc)}

    def enviar_inbound(self, mensagens: list[MensagemEntrante]) -> dict:
        if not mensagens:
            return {"ok": True, "aceitas": 0}
        payload = {"mensagens": [asdict(m) for m in mensagens]}
        try:
            r = self._http.post(f"{self.url}/api/bot/inbound", json=payload)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            return {"erro": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
        except Exception as exc:
            return {"erro": str(exc)}

    def buscar_outbound(self) -> list[dict]:
        try:
            r = self._http.get(f"{self.url}/api/bot/outbound")
            r.raise_for_status()
            return (r.json() or {}).get("pendentes", [])
        except Exception as exc:
            logger.warning("Falha ao buscar respostas pendentes: %s", exc)
            return []

    def confirmar(self, envio_id, ok: bool, erro: Optional[str] = None) -> None:
        corpo = {"ok": bool(ok)}
        if erro:
            corpo["erro"] = erro[:300]
        try:
            self._http.post(f"{self.url}/api/bot/outbound/{envio_id}/confirmar", json=corpo)
        except Exception as exc:
            logger.warning("Falha ao confirmar envio %s: %s", envio_id, exc)
