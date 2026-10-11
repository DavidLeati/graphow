"""Um `claude -p` falso: grava o que recebeu e imprime um stream-json gravado.

Os testes o rodam como executável da sessão, para provar o comando, a pasta, a
entrada e o ambiente sem chamar o Claude de verdade. O comportamento vem de
variáveis `GRAPHOW_TESTE_*` (as `CLAUDE*` a sessão apaga antes de lançar):

- `GRAPHOW_TESTE_REGISTRO`: pasta onde gravar, um JSON por chamada, os
  argumentos, a pasta de trabalho, a entrada padrão e o ambiente recebidos;
- `GRAPHOW_TESTE_STREAM`: o stream-json a imprimir (padrão: o da enxuta);
- `GRAPHOW_TESTE_DORMIR`: segundos de espera antes de imprimir o resultado;
- `GRAPHOW_TESTE_SAIDA`: o código de saída;
- `GRAPHOW_TESTE_COMMIT`: um ramo a criar na pasta de trabalho, com um commit;
- `GRAPHOW_TESTE_TRANSCRICOES`: pasta de projetos onde gravar a transcrição da
  sessão e a de um subagente, como o Claude Code grava em `~/.claude/projects`;
- `GRAPHOW_TESTE_FILHO`: abre um processo filho que dorme um minuto, como um
  servidor que o agente subiu; o PID dele vai para o registro.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

STREAM_PADRAO = Path(__file__).parent / "dados" / "stream_enxuta.jsonl"


def _registrar(entrada: str, filho: int | None) -> None:
    pasta = os.environ.get("GRAPHOW_TESTE_REGISTRO")
    if not pasta:
        return
    registro = {"argv": sys.argv[1:], "cwd": os.getcwd(), "stdin": entrada, "env": dict(os.environ),
                "pid": os.getpid(), "pid_do_filho": filho}
    destino = Path(pasta) / f"{uuid.uuid4().hex}.json"
    destino.write_text(json.dumps(registro, ensure_ascii=False), encoding="utf-8")


def _commitar(ramo: str) -> None:
    subprocess.run(["git", "checkout", "-q", "-b", ramo], check=True)
    Path("entrega.txt").write_text("feito\n", encoding="utf-8")
    subprocess.run(["git", "add", "entrega.txt"], check=True)
    ambiente = {**os.environ, "GIT_AUTHOR_NAME": "Falso", "GIT_AUTHOR_EMAIL": "falso@teste.invalid",
                "GIT_COMMITTER_NAME": "Falso", "GIT_COMMITTER_EMAIL": "falso@teste.invalid"}
    subprocess.run(["git", "commit", "-q", "-m", "Entrega falsa"], check=True, env=ambiente)


def _transcrever(pasta: str, linhas: list[str]) -> None:
    eventos = [json.loads(linha) for linha in linhas if linha.strip()]
    sessao = next(evento["session_id"] for evento in eventos if evento.get("session_id"))
    projeto = Path(pasta) / "C--bancada-falso"
    principal = [evento for evento in eventos if evento.get("type") == "assistant"]
    (projeto / sessao / "subagents").mkdir(parents=True, exist_ok=True)
    (projeto / f"{sessao}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in principal), encoding="utf-8")
    subagente = {"type": "assistant", "message": {"id": "msg_sub", "usage": {"input_tokens": 1000, "output_tokens": 10}}}
    (projeto / sessao / "subagents" / "agent-a1.jsonl").write_text(json.dumps(subagente) + "\n", encoding="utf-8")


def _abrir_filho() -> int | None:
    if not os.environ.get("GRAPHOW_TESTE_FILHO"):
        return None
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"]).pid


def main() -> int:
    entrada = sys.stdin.buffer.read().decode("utf-8")
    _registrar(entrada, _abrir_filho())
    linhas = Path(os.environ.get("GRAPHOW_TESTE_STREAM") or STREAM_PADRAO).read_text(encoding="utf-8").splitlines(True)
    sys.stdout.buffer.write("".join(linhas[:-1]).encode("utf-8"))
    sys.stdout.flush()
    time.sleep(float(os.environ.get("GRAPHOW_TESTE_DORMIR") or 0))
    if os.environ.get("GRAPHOW_TESTE_COMMIT"):
        _commitar(os.environ["GRAPHOW_TESTE_COMMIT"])
    if os.environ.get("GRAPHOW_TESTE_TRANSCRICOES"):
        _transcrever(os.environ["GRAPHOW_TESTE_TRANSCRICOES"], linhas)
    sys.stdout.buffer.write(linhas[-1].encode("utf-8"))
    return int(os.environ.get("GRAPHOW_TESTE_SAIDA") or 0)


if __name__ == "__main__":
    sys.exit(main())
