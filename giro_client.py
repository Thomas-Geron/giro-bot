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

from version import __version__

logger = logging.getLogger(__name__)


class BotBloqueado(Exception):
    """O Giro recusou o bot: plano sem o Giro Bot, pagamento em atraso ou termo não aceito.
    Não adianta tentar de novo — o bot para e mostra a mensagem do Giro."""

    def __init__(self, mensagem: str, motivo: str):
        super().__init__(mensagem)
        self.motivo = motivo  # 'plano' | 'pagamento' | 'termo'


def _checar_bloqueio(r: httpx.Response) -> None:
    if r.status_code != 403:
        return
    try:
        dados = r.json() or {}
    except ValueError:
        return
    motivo = dados.get("motivo") or ("termo" if "termo" in dados else None)
    if motivo:
        raise BotBloqueado(dados.get("erro") or "O Giro não liberou o bot.", motivo)


def _erro(exc: httpx.HTTPStatusError) -> str:
    """Mensagem do próprio Giro quando houver (ex.: termo não aceito); senão o código HTTP."""
    try:
        msg = (exc.response.json() or {}).get("erro")
    except ValueError:
        msg = None
    return msg or f"HTTP {exc.response.status_code}"


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
            headers={"Authorization": f"Bearer {self.token}",
                     "User-Agent": f"GiroBot/{__version__}"},  # entra no registro do aceite
        )

    def fechar(self) -> None:
        self._http.close()

    def licenca(self) -> dict:
        """Confere no Giro se esta loja pode usar o Giro Bot (plano, pagamento e termo).
        Levanta BotBloqueado quando o Giro recusa; {'erro'} quando não dá para conferir."""
        try:
            r = self._http.get(f"{self.url}/api/bot/licenca", params={"bot": "giro_bot"})
            _checar_bloqueio(r)
            r.raise_for_status()
            return r.json()
        except BotBloqueado:
            raise
        except httpx.HTTPStatusError as exc:
            return {"erro": _erro(exc)}
        except Exception as exc:
            return {"erro": str(exc)}

    def termo(self) -> dict:
        """Texto e versão atual do termo de riscos (público no Giro)."""
        try:
            r = self._http.get(f"{self.url}/api/bot/termo")
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            return {"erro": _erro(exc)}
        except Exception as exc:
            return {"erro": str(exc)}

    def aceitar_termo(self, versao: str, nome: str) -> dict:
        """Registra no Giro o aceite feito nesta janela."""
        try:
            r = self._http.post(f"{self.url}/api/bot/aceite", json={"versao": versao, "nome": nome})
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            return {"erro": _erro(exc)}
        except Exception as exc:
            return {"erro": str(exc)}

    def veiculos(self) -> dict:
        """Estoque disponível da loja (para o simulador de financiamento).
        {'veiculos': [...]} ou {'erro': ...}; BotBloqueado se o Giro recusar."""
        try:
            r = self._http.get(f"{self.url}/api/bot/veiculos")
            _checar_bloqueio(r)
            r.raise_for_status()
            return r.json()
        except BotBloqueado:
            raise
        except httpx.HTTPStatusError as exc:
            return {"erro": _erro(exc)}
        except Exception as exc:
            return {"erro": str(exc)}

    def enviar_inbound(self, mensagens: list[MensagemEntrante]) -> dict:
        if not mensagens:
            return {"ok": True, "aceitas": 0}
        payload = {"mensagens": [asdict(m) for m in mensagens]}
        try:
            r = self._http.post(f"{self.url}/api/bot/inbound", json=payload)
            _checar_bloqueio(r)
            r.raise_for_status()
            return r.json()
        except BotBloqueado:
            raise
        except httpx.HTTPStatusError as exc:
            return {"erro": _erro(exc)}
        except Exception as exc:
            return {"erro": str(exc)}

    def buscar_outbound(self) -> list[dict]:
        try:
            r = self._http.get(f"{self.url}/api/bot/outbound")
            _checar_bloqueio(r)
            r.raise_for_status()
            return (r.json() or {}).get("pendentes", [])
        except BotBloqueado:
            raise
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
