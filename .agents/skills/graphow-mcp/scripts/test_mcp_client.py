"""Script utilitário para validar o ciclo de vida e aperto de mão do Graphow MCP stdio.

O script iniciava o servidor sem `--papel`, obrigatório desde o Passo 1: o
processo saía com erro de argumento e a primeira leitura terminava em
`JSONDecodeError`, sem dizer o que havia acontecido. Agora o papel é explícito,
a saída de erro do servidor é reportada, e a verificação inclui a recusa de
`responder_questao` por uma sessão de executor. Ver achado A-14.
"""

import json
import os
import subprocess
import sys
import tempfile

PAPEL_DA_SESSAO = "executor"
AUTOR_DA_SESSAO = "agente-teste"

FERRAMENTAS_ESPERADAS = (
    "ler_vista",
    "expandir_no",
    "propor_patch",
    "abrir_questao",
    "buscar",
    "proximas_tarefas",
    "assumir_tarefa",
    "liberar_tarefa",
    "minhas_questoes",
    "aguardar_resposta",
)


def abrir_servidor(caminho_banco):
    """Sobe o servidor stdio com a identidade fixada na linha de comando."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [os.path.abspath("src"), env.get("PYTHONPATH", "")]
    )
    comando = [
        sys.executable,
        "-m",
        "graphow.mcp.stdio_server",
        "--papel",
        PAPEL_DA_SESSAO,
        "--autor",
        AUTOR_DA_SESSAO,
        "--db",
        caminho_banco,
    ]
    return subprocess.Popen(
        comando,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )


def conversar(processo, requisicao):
    """Envia uma requisição JSON-RPC e devolve a resposta já desserializada."""
    processo.stdin.write(json.dumps(requisicao) + "\n")
    processo.stdin.flush()
    linha = processo.stdout.readline()
    if not linha:
        raise RuntimeError(
            "O servidor encerrou sem responder. Saida de erro:\n"
            + (processo.stderr.read() or "(vazia)")
        )
    return json.loads(linha)


def conferir_aperto_de_mao(processo):
    """Confirma o handshake e que o papel da sessão é anunciado ao cliente."""
    resposta = conversar(
        processo,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
        },
    )
    servidor = resposta.get("result", {}).get("serverInfo", {})
    assert servidor.get("name") == "graphow", resposta
    assert servidor.get("papelDaSessao") == PAPEL_DA_SESSAO, resposta
    print(f"   -> Aperto de mao concluido. Papel da sessao: {servidor['papelDaSessao']}")


def conferir_lista_de_ferramentas(processo):
    """Confere que as ferramentas esperadas estão publicadas ao agente."""
    resposta = conversar(
        processo, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    )
    nomes = [ferramenta["name"] for ferramenta in resposta["result"]["tools"]]
    ausentes = [nome for nome in FERRAMENTAS_ESPERADAS if nome not in nomes]
    assert not ausentes, f"Ferramentas ausentes: {ausentes}"
    print(f"   -> {len(nomes)} ferramentas publicadas.")


def chamar_ferramenta(processo, identificador, nome, argumentos):
    """Executa uma ferramenta e devolve o conteúdo estruturado da resposta."""
    resposta = conversar(
        processo,
        {
            "jsonrpc": "2.0",
            "id": identificador,
            "method": "tools/call",
            "params": {"name": nome, "arguments": argumentos},
        },
    )
    return json.loads(resposta["result"]["content"][0]["text"])


def conferir_busca(processo):
    """Executa uma busca vazia para exercitar o caminho de leitura."""
    conteudo = chamar_ferramenta(processo, 3, "buscar", {"termo": "teste"})
    assert conteudo.get("sucesso") is True, conteudo
    print("   -> Ferramenta 'buscar' executada com sucesso.")


def conferir_recusa_de_ferramenta_humana(processo):
    """A escalação só é encerrada pelo humano, e a recusa precisa ser visível."""
    conteudo = chamar_ferramenta(
        processo, 4, "responder_questao", {"id_questao": "quest-1", "resposta": "x"}
    )
    assert conteudo.get("sucesso") is False, conteudo
    assert "abrir_questao" in conteudo.get("erro", ""), conteudo
    print("   -> Recusa de 'responder_questao' confirmada para sessao de executor.")


def main():
    """Roda a bateria completa contra um banco temporário e descartável."""
    print("Iniciando teste do servidor stdio MCP do Graphow...")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as arquivo:
        caminho_banco = arquivo.name

    processo = abrir_servidor(caminho_banco)
    try:
        print("1. Enviando 'initialize'...")
        conferir_aperto_de_mao(processo)
        print("2. Enviando 'tools/list'...")
        conferir_lista_de_ferramentas(processo)
        print("3. Enviando 'tools/call' para 'buscar'...")
        conferir_busca(processo)
        print("4. Confirmando a recusa de 'responder_questao'...")
        conferir_recusa_de_ferramenta_humana(processo)
        print("\nTodos os testes do Graphow MCP stdio passaram.")
        return 0
    finally:
        processo.terminate()
        processo.wait()
        remover_banco(caminho_banco)


def remover_banco(caminho_banco):
    """Apaga o banco temporário sem deixar a limpeza mascarar o resultado."""
    if not os.path.exists(caminho_banco):
        return
    try:
        os.remove(caminho_banco)
    except OSError:
        pass


if __name__ == "__main__":
    sys.exit(main())
