"""Atualização automática via GitHub Releases.

Fluxo: descobre a última release publicada -> compara com a versão local ->
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

API_RELEASES = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
PAGINA_RELEASES = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
INSTALADOR = "GiroBot-Setup.exe"  # nome do asset publicado pelo release.yml


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
    """Descobre a última release. Nunca levanta exceção.

    Usa o redirecionamento da PÁGINA /releases/latest (-> /releases/tag/vX.Y.Z),
    não a API: a API sem login aceita só 60 consultas por hora por conexão
    (compartilhadas com tudo o que a rede usa) e o botão respondia "403 rate
    limit exceeded". A API só é usada para as notas, quando há versão nova.

    Retorna {ha_atualizacao, versao, url_instalador, notas, pagina} ou {erro}.
    """
    try:
        resp = httpx.head(PAGINA_RELEASES, timeout=timeout, follow_redirects=False)
    except Exception as exc:
        return {"erro": f"Sem conexão com o GitHub: {exc}"}
    destino = resp.headers.get("location", "")
    if "/releases/tag/" not in destino:
        return {"erro": f"Nenhuma versão publicada encontrada (HTTP {resp.status_code})."}

    tag = destino.rsplit("/releases/tag/", 1)[1].strip("/")
    nova = e_mais_nova(tag)
    return {
        "ha_atualizacao": nova,
        "versao": re.sub(r"^[vV]", "", tag),
        "url_instalador": f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/{tag}/{INSTALADOR}",
        "notas": _notas(tag, timeout) if nova else "",
        "pagina": destino,
    }


def _notas(tag: str, timeout: float) -> str:
    """Texto da release (opcional: sem ele a atualização segue normal)."""
    try:
        resp = httpx.get(f"{API_RELEASES}/tags/{tag}", timeout=timeout,
                         headers={"Accept": "application/vnd.github+json"})
        return (resp.json().get("body") or "").strip() if resp.status_code == 200 else ""
    except Exception:
        return ""


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


if __name__ == "__main__":
    assert e_mais_nova("v1.3.1", "1.2.1") and not e_mais_nova("v1.3.1", "1.3.1") and e_mais_nova("1.10.0", "1.9.9")
    res = checar()
    print(res)
    assert "erro" not in res and res["url_instalador"].endswith("/GiroBot-Setup.exe"), res
    assert httpx.head(res["url_instalador"], follow_redirects=True, timeout=30).status_code == 200
    print("updater ok")

