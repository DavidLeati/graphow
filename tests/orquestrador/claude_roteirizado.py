"""Um `claude -p` falso para o orquestrador: responde por papel, na ordem de um roteiro.

O papel sai do `--append-system-prompt-file` (o nome do prompt do pacote). O
roteiro (`GRAPHOW_TESTE_ROTEIRO`) é um JSON com uma lista de respostas por
papel; cada chamada consome a próxima do seu papel. Cada resposta pode:

- `saida`: o objeto que vai em `structured_output` (e, em texto, em `result`);
- `texto`: o `result` em texto, quando a saída estruturada não vem;
- `arquivos`: arquivos a escrever na pasta de trabalho antes de responder;
- `comandos`: comandos a rodar na pasta, com o ambiente recebido (a trava do
  git inclusive); o código e a saída de erro de cada um vão para o registro;
- `custo`: o custo desta invocação; numa sessão retomada o resultado traz o
  acumulado, como o Claude Code faz;
- `bash`: as chamadas da ferramenta Bash que o stream mostra: o comando (com o
  resultado `ok`), ou {comando, codigo, saida}; sem ele, os `comandos` declarados;
- `morrer`: sai com 1 sem evento `result`, como um processo que caiu;
- `limite`: o limite de uso da conta, como o Claude Code o mostra (o
  `rate_limit_event` recusado e o `result` com `usage_limit_reached`), e sai com 1;
- `sobrecarga`: o `result` com o erro 529 da API, e sai com 1;
- `levantar`: grava os arquivos e sai com 7 sem responder.

O que cada chamada recebeu (argumentos, pasta, entrada e parte do ambiente) vai
para `GRAPHOW_TESTE_REGISTRO`, um JSON numerado por chamada.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


def _ler_json(caminho: Path, padrao: object) -> object:
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.is_file() else padrao


def _valor(argv: list[str], opcao: str) -> str:
    return argv[argv.index(opcao) + 1] if opcao in argv else ""


def _proxima(papel: str) -> dict:
    roteiro = Path(os.environ["GRAPHOW_TESTE_ROTEIRO"])
    estado_path = roteiro.with_suffix(".estado.json")
    estado = _ler_json(estado_path, {"contadores": {}, "custos": {}})
    indice = estado["contadores"].get(papel, 0)
    respostas = _ler_json(roteiro, {}).get(papel, [])
    estado["contadores"][papel] = indice + 1
    estado_path.write_text(json.dumps(estado), encoding="utf-8")
    if indice >= len(respostas):
        return {"texto": f"roteiro sem resposta {indice} para {papel}", "erro": True}
    return respostas[indice]


def _acumular(sessao: str, custo: float) -> float:
    roteiro = Path(os.environ["GRAPHOW_TESTE_ROTEIRO"])
    estado_path = roteiro.with_suffix(".estado.json")
    estado = _ler_json(estado_path, {"contadores": {}, "custos": {}})
    total = estado["custos"].get(sessao, 0.0) + custo
    estado["custos"][sessao] = total
    estado_path.write_text(json.dumps(estado), encoding="utf-8")
    return total


def _registrar(dados: dict) -> None:
    pasta = Path(os.environ["GRAPHOW_TESTE_REGISTRO"])
    pasta.mkdir(parents=True, exist_ok=True)
    numero = len(list(pasta.glob("*.json"))) + 1
    (pasta / f"{numero:03d}.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


def _executar(resposta: dict) -> list[dict]:
    for nome, conteudo in resposta.get("arquivos", {}).items():
        destino = Path(nome)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8", newline="\n")
    feitos = []
    for comando in resposta.get("comandos", []):
        feito = subprocess.run(comando, capture_output=True, text=True, check=False)
        feitos.append({"comando": comando, "codigo": feito.returncode, "erro": feito.stderr})
    return feitos


def _imprimir_chamadas_bash(resposta: dict) -> None:
    saida = resposta.get("saida") if isinstance(resposta.get("saida"), dict) else {}
    declarados = [str(item.get("comando", "")) for item in saida.get("comandos", []) if isinstance(item, dict)]
    for indice, item in enumerate(resposta.get("bash", declarados)):
        comando, codigo, saida = (item["comando"], item.get("codigo", 0), item.get("saida", "")) if isinstance(item, dict) else (item, 0, "ok")
        chamada = {"type": "tool_use", "id": f"toolu_{indice}", "name": "Bash", "input": {"command": comando}}
        print(json.dumps({"type": "assistant", "message": {"content": [chamada]}}), flush=True)
        conteudo = f"Exit code {codigo}\n{saida}" if codigo else saida
        retorno = {"type": "tool_result", "tool_use_id": f"toolu_{indice}", "content": conteudo, "is_error": bool(codigo)}
        print(json.dumps({"type": "user", "message": {"content": [retorno]}}), flush=True)


def _erro_da_api(sessao: str, resposta: dict) -> int:
    if resposta.get("limite"):
        informacao = {"status": "rejected", "resetsAt": 1791812400, "rateLimitType": "five_hour"}
        print(json.dumps({"type": "rate_limit_event", "rate_limit_info": informacao, "session_id": sessao}), flush=True)
    erro, status = ("usage_limit_reached", 429) if resposta.get("limite") else ("overloaded_error", 529)
    print(json.dumps({"type": "result", "subtype": "success", "is_error": True, "session_id": sessao, "result": "API Error",
                      "total_cost_usd": 0, "num_turns": 1, "duration_ms": 5, "api_error": erro, "api_error_status": status,
                      "terminal_reason": "api_error"}), flush=True)
    return 1


def main() -> int:
    argv = sys.argv[1:]
    entrada = sys.stdin.buffer.read().decode("utf-8")
    papel = Path(_valor(argv, "--append-system-prompt-file")).stem or "desconhecido"
    resposta = _proxima(papel)
    sessao = _valor(argv, "--resume") or str(uuid.uuid4())
    feitos = _executar(resposta)
    ambiente = {nome: valor for nome, valor in os.environ.items() if nome.startswith(("GIT_CONFIG", "GRAPHOW_DB"))}
    _registrar({"papel": papel, "argv": argv, "cwd": os.getcwd(), "stdin": entrada, "ambiente": ambiente,
                "tem_claude": any(nome.upper().startswith("CLAUDE") for nome in os.environ), "comandos": feitos})
    if resposta.get("levantar"):
        return 7
    print(json.dumps({"type": "system", "subtype": "init", "session_id": sessao, "model": "claude-teste"}), flush=True)
    if resposta.get("morrer"):
        return 1
    if resposta.get("limite") or resposta.get("sobrecarga"):
        return _erro_da_api(sessao, resposta)
    _imprimir_chamadas_bash(resposta)
    saida = resposta.get("saida")
    texto = resposta.get("texto") or (json.dumps(saida) if saida is not None else "")
    uso = {"claude-teste": {"inputTokens": 10, "outputTokens": 5, "cacheReadInputTokens": 100, "cacheCreationInputTokens": 20}}
    resultado = {
        "type": "result", "subtype": "error_during_execution" if resposta.get("erro") else "success",
        "is_error": bool(resposta.get("erro")), "session_id": sessao, "result": texto,
        "total_cost_usd": _acumular(sessao, float(resposta.get("custo", 0.1))), "num_turns": 3, "duration_ms": 10,
        "modelUsage": uso,
    }
    if saida is not None:
        resultado["structured_output"] = saida
    print(json.dumps(resultado), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
