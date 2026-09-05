"""Fábrica de canais: monta só os canais pedidos no .env."""
import logging

import config
from canais.base import Canal

logger = logging.getLogger(__name__)


def criar_canais(nomes: list[str], headless: bool = False) -> tuple[dict[str, Canal], object]:
    """Devolve ({nome: canal}, navegador_ou_None).

    O navegador só é aberto se algum canal precisar dele.
    """
    precisa_navegador = any(n in ("whatsapp", "olx") for n in nomes)
    navegador = None
    if precisa_navegador:
        from canais.navegador import Navegador
        navegador = Navegador(config.PERFIL_DIR, headless=headless)
        navegador.abrir()

    canais: dict[str, Canal] = {}
    for nome in nomes:
        if nome == "simulado":
            from canais.simulado import CanalSimulado
            canais[nome] = CanalSimulado()
        elif nome == "whatsapp":
            from canais.whatsapp import CanalWhatsApp
            canais[nome] = CanalWhatsApp(navegador)
        elif nome == "olx":
            from canais.olx import CanalOlx
            canais[nome] = CanalOlx(navegador)
        else:
            logger.warning("Canal desconhecido ignorado: %s", nome)
    return canais, navegador
