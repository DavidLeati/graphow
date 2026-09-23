"""Cabeçalhos de escrita no servidor do canvas, lidos do jeito que a página os lê."""

import json
import urllib.parse
import urllib.request


def cabecalhos_de_escrita(url: str) -> dict[str, str]:
    """O tipo JSON e o token da sessão, lido de `/api/identity` do servidor da URL."""
    partes = urllib.parse.urlsplit(url)
    with urllib.request.urlopen(f"{partes.scheme}://{partes.netloc}/api/identity") as resposta:
        token = json.loads(resposta.read().decode("utf-8"))["token"]
    return {"Content-Type": "application/json", "X-Graphow-Token": token}
