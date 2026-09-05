"""Interface comum a todos os canais do bot."""
from abc import ABC, abstractmethod

from giro_client import MensagemEntrante


class Canal(ABC):
    """Um canal é uma fonte/destino de mensagens (WhatsApp, OLX, ...).

    O bot só conhece esta interface — trocar/adicionar canal não mexe no loop.
    """

    nome: str = "base"

    @abstractmethod
    def iniciar(self) -> None:
        """Abre o que for preciso (navegador, sessão). Pode pedir login na 1a vez."""

    @abstractmethod
    def ler_novas(self) -> list[MensagemEntrante]:
        """Devolve as mensagens recebidas ainda não enviadas ao Giro.

        Deve ser idempotente do lado do Giro: sempre preencher `msg_id` com um
        identificador estável da mensagem no canal.
        """

    @abstractmethod
    def enviar(self, thread_id: str, texto: str) -> None:
        """Envia a resposta na conversa. Deve levantar exceção se falhar."""

    def encerrar(self) -> None:
        """Fecha recursos. Sobrescreva se necessário."""
        return None
