"""Configuração do Giro Bot.

Guardada em %APPDATA%/GiroBot/config.json (Windows) — o usuário edita pela
janela do programa, nunca por arquivo. O .env continua funcionando para
desenvolvimento (tem prioridade se existir).
"""
import json
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

if os.name == "nt":
    CONFIG_DIR = Path(os.getenv("APPDATA") or Path.home()) / "GiroBot"
else:
    CONFIG_DIR = Path.home() / ".girobot"

CONFIG_FILE = CONFIG_DIR / "config.json"
PERFIL_DIR = CONFIG_DIR / "perfil"      # sessão do navegador (login salvo)

PADRAO = {
    "giro_url": "https://revendedora-web.onrender.com",
    "token": "",
    "canais": ["simulado"],
    "poll_segundos": 15,
    "headless": False,
}


def carregar() -> dict:
    """Config salva, com .env sobrepondo quando presente (modo dev)."""
    dados = dict(PADRAO)
    if CONFIG_FILE.exists():
        try:
            dados.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass

    env = RAIZ / ".env"
    if env.exists():
        try:
            from dotenv import dotenv_values
            valores = dotenv_values(env)
            if valores.get("GIRO_URL"):
                dados["giro_url"] = valores["GIRO_URL"].rstrip("/")
            if valores.get("GIRO_BOT_TOKEN"):
                dados["token"] = valores["GIRO_BOT_TOKEN"]
            if valores.get("CANAIS"):
                dados["canais"] = [c.strip() for c in valores["CANAIS"].split(",") if c.strip()]
            if valores.get("POLL_SEGUNDOS"):
                dados["poll_segundos"] = int(valores["POLL_SEGUNDOS"])
        except Exception:
            pass

    dados["giro_url"] = (dados.get("giro_url") or "").rstrip("/")
    return dados


def salvar(dados: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    atual = carregar()
    atual.update(dados)
    atual["giro_url"] = (atual.get("giro_url") or "").rstrip("/")
    CONFIG_FILE.write_text(json.dumps(atual, indent=2, ensure_ascii=False), encoding="utf-8")


def validar(dados: dict) -> list[str]:
    erros = []
    if not dados.get("giro_url"):
        erros.append("Informe o endereço do Giro.")
    if not dados.get("token"):
        erros.append("Cole o token do bot (gere no Giro, em Bot).")
    if not dados.get("canais"):
        erros.append("Escolha ao menos um canal.")
    return erros
