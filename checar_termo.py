"""Confere a janela do termo de riscos (sem internet: o Giro é simulado).
Rodar:  python checar_termo.py   (abre e fecha janelas sozinho por alguns segundos)"""
import sys
import tempfile
from pathlib import Path

import config

PASTA = Path(tempfile.mkdtemp())
config.CONFIG_DIR, config.CONFIG_FILE, config.LOG_FILE = PASTA, PASTA / "config.json", PASTA / "bot.log"

import gui  # noqa: E402  (depois de apontar a configuração para a pasta temporária)

TERMO = {"versao": "v1", "versao_legivel": "01/01/2030", "titulo": "Termo de teste",
         "riscos": [{"titulo": "Risco A", "texto": "a"}, {"titulo": "Risco B", "texto": "b"}],
         "secoes": [{"titulo": "1. O que é", "paragrafos": ["texto"]}],
         "declaracoes": ["Declaração um", "Declaração dois", "Declaração três"]}
aceites, falhas = [], []


class GiroFalso:
    termo_atual = TERMO

    def __init__(self, *_):
        pass

    def termo(self):
        return self.termo_atual

    def aceitar_termo(self, versao, nome):
        aceites.append((versao, nome))
        return {"ok": True}

    def fechar(self):
        pass


def checar(cond, msg):
    print(("  OK   " if cond else "  FALHA ") + msg)
    if not cond:
        falhas.append(msg)


def dialogo(app):
    return next(w for w in app.winfo_children() if w.winfo_class() == "Toplevel")


def widgets(janela, classe):
    achados, fila = [], [janela]
    while fila:
        w = fila.pop()
        fila.extend(w.winfo_children())
        if w.winfo_class() == classe:
            achados.append(w)
    return achados


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    gui.GiroClient = GiroFalso
    gui.messagebox.showerror = lambda *a, **k: None
    app = gui.App()
    app.withdraw()
    cfg = {"giro_url": "http://giro.teste", "token": "t", "canais": ["simulado"]}

    print("[aviso fixo]")
    checar("Seu número pode ser bloqueado" in app.lbl_riscos.cget("text"), "a janela abre com os riscos à vista, mesmo sem internet")

    print("[primeiro início: termo obrigatório]")
    passos = {}

    def interagir():
        j = dialogo(app)
        caixas = widgets(j, "Checkbutton")
        entrada = widgets(j, "TEntry")[0]
        aceito = next(b for b in widgets(j, "TButton") if "aceito" in str(b.cget("text")) and "Não" not in str(b.cget("text")))
        passos["inicio"] = str(aceito.cget("state"))
        for c in caixas[:-1]:
            c.invoke()
        entrada.insert(0, "Maria Silva")
        app.update()
        passos["faltando_caixa"] = str(aceito.cget("state"))
        caixas[-1].invoke()
        entrada.delete(0, "end"); entrada.insert(0, "Maria")
        app.update()
        passos["sem_sobrenome"] = str(aceito.cget("state"))
        entrada.delete(0, "end"); entrada.insert(0, "Maria Silva")
        app.update()
        passos["pronto"] = str(aceito.cget("state"))
        aceito.invoke()

    app.after(300, interagir)
    ok = app._termo_aceito(cfg)
    checar(passos.get("inicio") == "disabled", "o botão de aceitar começa desligado")
    checar(passos.get("faltando_caixa") == "disabled", "com uma declaração sem marcar, continua desligado")
    checar(passos.get("sem_sobrenome") == "disabled", "sem sobrenome, continua desligado")
    checar(passos.get("pronto") == "normal", "tudo marcado e nome completo: liga")
    checar(ok and aceites == [("v1", "Maria Silva")], f"aceite registrado no Giro ({aceites})")
    checar(config.carregar().get("termo_versao") == "v1", "e guardado nesta janela")
    checar("Risco A" in app.lbl_riscos.cget("text"), "o aviso fixo passa a usar os riscos do Giro")

    print("[mesma versão: não pergunta de novo]")
    checar(app._termo_aceito(cfg) and len(aceites) == 1, "já aceito: inicia direto")

    print("[termo mudou: pergunta de novo]")
    GiroFalso.termo_atual = {**TERMO, "versao": "v2"}

    def recusar():
        j = dialogo(app)
        next(b for b in widgets(j, "TButton") if str(b.cget("text")) == "Não aceito").invoke()

    app.after(300, recusar)
    checar(not app._termo_aceito(cfg), "versão nova recusada: o bot não inicia")
    checar(config.carregar().get("termo_versao") == "v1", "o aceite antigo não vale para a versão nova")

    print("[Giro fora do ar]")
    GiroFalso.termo_atual = {"erro": "sem conexão"}
    checar(not app._termo_aceito(cfg), "sem conseguir ler o termo, o bot não inicia")

    app.destroy()
    print("\nRESULTADO:", "TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)")
    for f in falhas:
        print(" -", f)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
