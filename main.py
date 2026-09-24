"""Giro Bot — modo linha de comando (para desenvolvimento).

Usuário final deve usar a janela: `python gui.py` (ou o GiroBot.exe).
"""
import logging
import sys

import config
from runner import Runner

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
config.configurar_log()


def main() -> int:
    cfg = config.carregar()
    erros = config.validar(cfg)
    if erros:
        for e in erros:
            print("ERRO:", e)
        return 1

    runner = Runner(cfg)  # o logging já mostra no terminal e grava no arquivo
    runner.iniciar()
    try:
        while runner.rodando:
            runner.aguardar(1)
    except KeyboardInterrupt:
        print("Encerrando…")
        runner.parar()
        runner.aguardar(30)
    return 0


if __name__ == "__main__":
    sys.exit(main())
