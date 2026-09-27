"""Confere a licença do Giro Bot (sem rede: o Giro é simulado).
Rodar:  python checar_licenca.py

Regra: o bot só funciona com plano que inclua o Giro Bot, pagamento em dia e termo
aceito; sem conseguir conferir no Giro (sem internet), não inicia; recusado no meio
do caminho, para."""
import sys
import tempfile
from pathlib import Path

import httpx

import config

PASTA = Path(tempfile.mkdtemp())
config.CONFIG_DIR, config.CONFIG_FILE, config.LOG_FILE = PASTA, PASTA / "config.json", PASTA / "bot.log"

import giro_client  # noqa: E402
import runner  # noqa: E402
from giro_client import BotBloqueado  # noqa: E402

falhas = []
CFG = {"giro_url": "http://giro.teste", "token": "t", "canais": ["simulado"], "poll_segundos": 5}


def checar(cond, msg):
    print(("  OK   " if cond else "  FALHA ") + msg)
    if not cond:
        falhas.append(msg)


class GiroFalso:
    licenca_resposta = {"liberado": True, "loja": "Loja Teste"}
    bloquear_no_ciclo = None

    def __init__(self, *_):
        pass

    def licenca(self):
        if isinstance(self.licenca_resposta, BotBloqueado):
            raise self.licenca_resposta
        return self.licenca_resposta

    def enviar_inbound(self, novas):
        return {"ok": True}

    def buscar_outbound(self):
        if self.bloquear_no_ciclo:
            raise self.bloquear_no_ciclo
        return []

    def confirmar(self, *a):
        pass

    def fechar(self):
        pass


def rodar():
    msgs = []
    r = runner.Runner(dict(CFG), log=msgs.append)
    r.iniciar()
    r.aguardar(20)
    return r, msgs


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    runner.GiroClient = GiroFalso

    print("[resposta do Giro]")

    def resposta(codigo, corpo):
        return httpx.Response(codigo, json=corpo, request=httpx.Request("GET", "http://x"))
    for corpo, motivo in (({"motivo": "plano", "erro": "plano"}, "plano"),
                          ({"motivo": "pagamento", "erro": "pag"}, "pagamento"),
                          ({"erro": "aceite o termo", "termo": "v1"}, "termo")):
        try:
            giro_client._checar_bloqueio(resposta(403, corpo))
            checar(False, f"403 {motivo} vira bloqueio")
        except BotBloqueado as exc:
            checar(exc.motivo == motivo, f"403 {motivo} vira bloqueio")
    try:
        giro_client._checar_bloqueio(resposta(403, {"erro": "outro"}))
        giro_client._checar_bloqueio(resposta(200, {}))
        checar(True, "outras respostas não bloqueiam")
    except BotBloqueado:
        checar(False, "outras respostas não bloqueiam")
    cli = giro_client.GiroClient("http://127.0.0.1:9", "t", timeout=2)
    checar("erro" in cli.licenca(), "sem conexão: licença volta com erro (não libera)")
    cli.fechar()

    print("[plano sem o Giro Bot]")
    GiroFalso.licenca_resposta = BotBloqueado("O Giro Bot faz parte do plano Loja ou superior.", "plano")
    r, msgs = rodar()
    checar(not r.rodando and r.bloqueio == "plano", "não inicia")
    checar(any(m.startswith("Bot bloqueado: O Giro Bot faz parte") for m in msgs), "e explica o motivo")
    checar(not any("pronto" in m for m in msgs), "nenhum canal é aberto")

    print("[sem internet]")
    GiroFalso.licenca_resposta = {"erro": "sem conexão"}
    r, msgs = rodar()
    checar(not r.rodando and not r.bloqueio, "não inicia")
    checar(any("Sem conferir o plano no Giro o bot não inicia" in m for m in msgs), "e diz por quê")

    print("[pagamento vence com o bot rodando]")
    GiroFalso.licenca_resposta = {"liberado": True, "loja": "Loja Teste"}
    GiroFalso.bloquear_no_ciclo = BotBloqueado("O acesso da loja está bloqueado por falta de pagamento.", "pagamento")
    r, msgs = rodar()
    checar(any("Conectado ao Giro como: Loja Teste" in m for m in msgs), "começou normalmente")
    checar(not r.rodando and r.bloqueio == "pagamento", "para sozinho quando o Giro recusa")
    checar(msgs[-1] == "Bot parado.", "e fecha tudo")

    print("[Testar conexão]")
    GiroFalso.licenca_resposta = BotBloqueado("plano", "plano")
    res = runner.Runner(dict(CFG)).testar_conexao()
    checar(res.get("bloqueio") == "plano" and res.get("erro") == "plano", "mostra o bloqueio no teste")

    print("\nRESULTADO:", "TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
