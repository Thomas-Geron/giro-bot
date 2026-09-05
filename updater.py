"""Atualização automática via GitHub Releases.

Fluxo: consulta a última release publicada -> compara com a versão local ->
se houver versão nova, baixa o instalador (asset .exe) e executa. O
instalador substitui a instalação atual e reabre o programa.

Nada é baixado sem o usuário aceitar.
"""
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional

import httpx

from version import GITHUB_OWNER, GITHUB_REPO, __version__

logger = logging.getLogger(__name__)

API_RELEASE = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
PAGINA_RELEASES = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


def _tupla(versao: str) -> tuple:
    """'v1.2.3' -> (1, 2, 3). Partes não numéricas viram 0."""
    limpo = re.sub(r"^[vV]", "", (versao or "").strip())
    partes = re.split(r"[.\-+]", limpo)
    numeros = []
    for p in partes[:4]:
        try:
            numeros.append(int(p))
        except ValueError:
            break
    while len(numeros) < 3:
        numeros.append(0)
    return tuple(numeros)


def e_mais_nova(remota: str, local: str = __version__) -> bool:
    return _tupla(remota) > _tupla(local)


def checar(timeout: float = 10.0) -> dict:
    """Consulta a última release. Nunca levanta exceção.

    Retorna {ha_atualizacao, versao, url_instalador, notas, pagina} ou {erro}.
    """
    try:
        resp = httpx.get(
            API_RELEASE,
            headers={"Accept": "application/vnd.github+json"},
            timeout=timeout,
            follow_redirects=True,
        )
        if resp.status_code == 404:
            return {"erro": "Nenhuma versão publicada ainda."}
        resp.raise_for_status()
        dados = resp.json() or {}
    except Exception as exc:
        return {"erro": str(exc)}

    tag = str(dados.get("tag_name") or "")
    if not tag:
        return {"erro": "Release sem tag."}

    url_exe = None
    for asset in dados.get("assets") or []:
        nome = str(asset.get("name") or "")
        if nome.lower().endswith(".exe"):
            url_exe = asset.get("browser_download_url")
            break

    return {
        "ha_atualizacao": e_mais_nova(tag),
        "versao": re.sub(r"^[vV]", "", tag),
        "url_instalador": url_exe,
        "notas": (dados.get("body") or "").strip(),
        "pagina": dados.get("html_url") or PAGINA_RELEASES,
    }


def baixar_instalador(url: str, progresso: Optional[Callable[[int], None]] = None) -> Path:
    """Baixa o instalador para a pasta temporária e devolve o caminho."""
    destino = Path(tempfile.gettempdir()) / "GiroBot-Setup.exe"
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        baixado = 0
        with destino.open("wb") as f:
            for bloco in r.iter_bytes(chunk_size=65536):
                f.write(bloco)
                baixado += len(bloco)
                if progresso and total:
                    progresso(int(baixado * 100 / total))
    return destino


def executar_instalador(caminho: Path) -> None:
    """Dispara o instalador. O chamador DEVE fechar o app em seguida — um
    programa aberto não pode ser sobrescrito por ele mesmo."""
    if os.name != "nt":
        raise RuntimeError("Atualização automática disponível apenas no Windows.")
    subprocess.Popen([str(caminho)], close_fds=True)
