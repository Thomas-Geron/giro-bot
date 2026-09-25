"""Confere o aviso de versão nova na janela (sem rede: o GitHub é simulado).
Rodar:  python checar_atualizacao.py"""
import sys
import tempfile
from pathlib import Path

import config

PASTA = Path(tempfile.mkdtemp())
config.CONFIG_DIR, config.CONFIG_FILE, config.LOG_FILE = PASTA, PASTA / "config.json", PASTA / "bot.log"

import gui  # noqa: E402  (depois de apontar a configuração para a pasta temporária)

NOVA = {"ha_atualizacao": True, "versao": "9.9.9", "url_instalador": "https://x/GiroBot-Setup.exe",
        "notas": "", "pagina": "https://x"}
falhas, perguntas = [], []


def checar(cond, msg):
    print(("  OK   " if cond else "  FALHA ") + msg)
    if not cond:
        falhas.append(msg)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    gui.updater.checar = lambda *a, **k: {"ha_atualizacao": False, "versao": gui.__version__}
    gui.messagebox.askyesno = lambda *a, **k: perguntas.append(a) or False
    app = gui.App()
    app.withdraw()
    app.update()
    visivel = lambda: bool(app.aviso_versao.grid_info())  # noqa: E731
    checar(not visivel(), "sem versão nova, sem aviso")

    print("[conferência periódica]")
    app._resultado_atualizacao(NOVA, silencioso=True, perguntar=False)
    checar(visivel() and "9.9.9" in app.aviso_versao.rotulo.cget("text"), "o aviso aparece sozinho, com a versão")
    checar(not perguntas, "e não abre janela (o bot pode estar rodando sozinho)")
    app._resultado_atualizacao(NOVA, silencioso=True, perguntar=False)
    registro = app.log.texto.get("1.0", "end")
    checar(registro.count("Nova versão disponível: v9.9.9") == 1, "a mesma versão não repete no registro")

    print("[ao abrir / botão]")
    app._resultado_atualizacao(NOVA, silencioso=True, perguntar=True)
    checar(len(perguntas) == 1, "oferece instalar")
    checar(visivel() and "adiada" in app.log.texto.get("1.0", "end"), "recusou: o aviso continua no topo")

    app.destroy()
    print("\nRESULTADO:", "TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
