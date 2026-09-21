"""Testes de integração da execução de subcomandos da linha de comando."""

import io
import json
from pathlib import Path

import pytest

from graphow.api.cli_execucao import CODIGO_SUCESSO, ExecutorLinhaDeComando
from graphow.api.cli_parser import construir_parser
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.storage.localizador_banco import AmbienteEmMemoria, LocalizadorBancoEventos
from graphow.storage.sqlite_store import SQLiteEventStore


def _executar(argumentos: list[str], diretorio_dados: Path) -> tuple[int, EscritorConsoleEmMemoria]:
    """Executa um subcomando com o diretório de dados apontado para um caminho temporário."""
    console = EscritorConsoleEmMemoria()
    ambiente = AmbienteEmMemoria({"LOCALAPPDATA": str(diretorio_dados)}, diretorio_dados)
    executor = ExecutorLinhaDeComando(console, LocalizadorBancoEventos(ambiente))
    return executor.executar(construir_parser().parse_args(argumentos)), console


def test_banco_info_mostra_caminho_resolvido_nominal(tmp_path: Path) -> None:
    """O comando de diagnóstico revela onde o banco será aberto."""
    codigo, console = _executar(["banco-info"], tmp_path)
    assert codigo == CODIGO_SUCESSO
    assert any("graphow.db" in linha for linha in console.linhas)
    assert not any("AVISO" in linha for linha in console.linhas)


def test_banco_info_alerta_quando_caminho_esta_no_onedrive_edge_case(tmp_path: Path) -> None:
    """Caso de borda: caminho explícito em pasta de nuvem dispara o alerta."""
    caminho_arriscado = str(tmp_path / "OneDrive" / "Documentos" / "graphow.db")
    codigo, console = _executar(["--db", caminho_arriscado, "banco-info"], tmp_path)
    assert codigo == CODIGO_SUCESSO
    assert any("AVISO" in linha for linha in console.linhas)


def test_init_cria_o_banco_no_diretorio_de_dados_nominal(tmp_path: Path) -> None:
    """O comando de inicialização cria diretório e arquivo do banco."""
    codigo, console = _executar(["init"], tmp_path)
    assert codigo == CODIGO_SUCESSO
    assert (tmp_path / "graphow" / "graphow.db").is_file()
    assert any("inicializado" in linha for linha in console.linhas)


def test_migracao_copia_eventos_do_banco_antigo_nominal(tmp_path: Path) -> None:
    """A migração preserva os eventos e mantém a origem intacta."""
    origem = tmp_path / "antigo" / "graphow.db"
    origem.parent.mkdir(parents=True)
    with SQLiteEventStore(str(origem)) as store:
        _popular(store)

    codigo, console = _executar(["migrar-banco", "--origem", str(origem)], tmp_path)
    assert codigo == CODIGO_SUCESSO
    assert any("Migrados 3 eventos" in linha for linha in console.linhas)
    assert origem.is_file()
    assert (tmp_path / "graphow" / "graphow.db").is_file()


def test_migracao_nao_sobrescreve_banco_existente_edge_case(tmp_path: Path) -> None:
    """Caso de borda: destino já povoado não é sobrescrito pela migração."""
    _executar(["init"], tmp_path)
    origem = tmp_path / "antigo.db"
    with SQLiteEventStore(str(origem)) as store:
        _popular(store)

    codigo, console = _executar(["migrar-banco", "--origem", str(origem)], tmp_path)
    assert codigo == CODIGO_SUCESSO
    assert any("nao realizada" in linha for linha in console.linhas)


def test_migracao_de_origem_inexistente_nao_falha_edge_case(tmp_path: Path) -> None:
    """Caso de borda: origem ausente devolve mensagem clara em vez de exceção."""
    codigo, console = _executar(["migrar-banco", "--origem", str(tmp_path / "nada.db")], tmp_path)
    assert codigo == CODIGO_SUCESSO
    assert any("Origem inexistente" in linha for linha in console.linhas)


def test_task_create_e_task_list_persistem_entre_execucoes_nominal(tmp_path: Path) -> None:
    """Duas execuções distintas compartilham o mesmo banco resolvido."""
    _criar_sessao_no_banco(tmp_path)
    codigo_criacao, console_criacao = _executar(
        ["task-create", "--titulo", "Escrever documentacao", "--sessao", "sess-1"], tmp_path
    )
    assert codigo_criacao == CODIGO_SUCESSO
    assert any("Task criada com sucesso" in linha for linha in console_criacao.linhas)

    _, console_listagem = _executar(["task-list"], tmp_path)
    assert any("Escrever documentacao" in linha for linha in console_listagem.linhas)


def _criar_sessao_no_banco(diretorio_dados: Path) -> None:
    """Prepara uma Sessão no banco resolvido, para as tarefas terem onde nascer."""
    from graphow.core.types import PapelAutor, TipoAresta, TipoNo
    from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
    from graphow.kernel.write_kernel import WriteKernel

    nos = (
        ("proj-1", TipoNo.PROJETO, "Projeto 1"),
        ("setor-1", TipoNo.SETOR, "Setor 1"),
        ("sess-1", TipoNo.SESSAO, "Sessao 1"),
    )
    arestas = (("contem-proj-setor", "proj-1", "setor-1"), ("contem-setor-sessao", "setor-1", "sess-1"))
    operacoes = [
        ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value={"id": id_no, "tipo": tipo.value, "rotulo": rotulo})
        for id_no, tipo, rotulo in nos
    ]
    operacoes.extend(
        ItemPatch(
            op=OperacaoPatch.ADD,
            path=f"/arestas/{id_aresta}",
            value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": TipoAresta.CONTEM.value},
        )
        for id_aresta, origem, destino in arestas
    )

    caminho = diretorio_dados / "graphow" / "graphow.db"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with SQLiteEventStore(str(caminho)) as store:
        WriteKernel(store).submeter_patch(
            PropostaPatch.criar(DadosPropostaPatch("david", PapelAutor.HUMANO, operacoes))
        )


def _executar_com_payload(
    argumentos: list[str],
    diretorio_dados: Path,
    payload: str,
) -> tuple[int, EscritorConsoleEmMemoria]:
    """Executa um subcomando com o JSON do hook posto na entrada padrão."""
    with pytest.MonkeyPatch.context() as ambiente:
        ambiente.setattr("sys.stdin", io.StringIO(payload))
        return _executar(argumentos, diretorio_dados)


def test_harness_le_a_sessao_do_payload_do_hook_nominal(tmp_path: Path) -> None:
    """O id da sessão chega no JSON da entrada padrão, não em variável de ambiente."""
    codigo, console = _executar_com_payload(
        ["harness", "--fase", "inicio", "--entrada-hook"],
        tmp_path,
        '{"session_id": "sess-do-hook", "model": "claude-opus-5", "source": "startup"}',
    )

    assert codigo == CODIGO_SUCESSO
    assert any("run-sess-do-hook" in linha for linha in console.linhas)


def test_harness_sem_setor_abre_a_sessao_no_ambiente_padrao_do_repositorio_nominal(tmp_path: Path) -> None:
    """O hook não precisa de um Setor criado à parte: o repositório em que rodou é o ambiente.

    O `cwd` do payload nomeia o Projeto; o Setor `Memoria` nasce dentro dele na
    primeira sessão. Antes, sem `--setor`, o comando só gravava telemetria.
    """
    from graphow.core.types import TipoNo
    from graphow.kernel.write_kernel import WriteKernel

    repositorio = tmp_path / "meu-repo"
    (repositorio / ".git").mkdir(parents=True)
    payload = json.dumps({"session_id": "sess-do-hook", "cwd": str(repositorio), "source": "startup"})

    codigo, console = _executar_com_payload(["harness", "--fase", "inicio", "--entrada-hook"], tmp_path, payload)

    assert codigo == CODIGO_SUCESSO
    assert any("no setor setor-meu-repo-memoria" in linha for linha in console.linhas)
    with SQLiteEventStore(str(tmp_path / "graphow" / "graphow.db")) as store:
        view = WriteKernel(store).obter_view()
    assert view.obter_no("proj-meu-repo").tipo == TipoNo.PROJETO
    assert [no.id for no in view.obter_filhos_por_contencao("setor-meu-repo-memoria")] == ["sess-do-hook"]


def test_harness_sem_sessao_no_payload_recusa_em_vez_de_estourar_edge_case(tmp_path: Path) -> None:
    """Caso de borda: era aqui que o comando terminava em IndexError no SchemaGate."""
    codigo, console = _executar_com_payload(
        ["harness", "--fase", "inicio", "--entrada-hook", "--setor", "setor-1"], tmp_path, "{}"
    )

    assert codigo == 1
    assert any("session_id" in linha for linha in console.linhas)


def test_harness_com_payload_ilegivel_recusa_edge_case(tmp_path: Path) -> None:
    """Caso de borda: payload quebrado é recusa explícita, não traceback."""
    codigo, _ = _executar_com_payload(
        ["harness", "--fase", "fim", "--entrada-hook"], tmp_path, "nao e json"
    )

    assert codigo == 1


def test_fim_pelo_harness_abre_a_tarefa_de_condensacao_no_banco_nominal(tmp_path: Path) -> None:
    """O hook de fim encerra a sessão e o grafo pede a condensação, no mesmo processo.

    O motor reativo só estava ligado no processo web: encerrar pelo hook não
    pedia nada. Aqui o subcomando roda sozinho, sem canvas aberto.
    """
    from graphow.core.types import TipoNo
    from graphow.kernel.write_kernel import WriteKernel
    from graphow.reactive.condensacao import eh_tarefa_de_condensacao

    _criar_sessao_no_banco(tmp_path)
    _executar(["task-create", "--titulo", "Trabalho feito", "--sessao", "sess-1"], tmp_path)

    codigo, _ = _executar(["harness", "--fase", "fim", "--sessao", "sess-1", "--resumo", "fim"], tmp_path)

    assert codigo == CODIGO_SUCESSO
    with SQLiteEventStore(str(tmp_path / "graphow" / "graphow.db")) as store:
        view = WriteKernel(store).obter_view()
    assert view.obter_no("sess-1").obter_propriedade("status") == "concluida"
    condensacoes = [no for no in view.listar_nos_por_tipo(TipoNo.TASK) if eh_tarefa_de_condensacao(no)]
    assert len(condensacoes) == 1


def _registrar_aprendizado_promovido_no_banco(diretorio_dados: Path) -> None:
    """Um aprendizado com origem e alcance no banco resolvido, para o acervo ter o que projetar."""
    from graphow.core.types import PapelAutor, TipoAresta, TipoNo
    from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
    from graphow.kernel.write_kernel import WriteKernel

    def no(id_no: str, tipo: TipoNo) -> ItemPatch:
        return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value={"id": id_no, "tipo": tipo.value, "rotulo": id_no})

    def aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
        id_aresta = f"{tipo.value}-{origem}-{destino}"
        return ItemPatch(
            op=OperacaoPatch.ADD,
            path=f"/arestas/{id_aresta}",
            value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value},
        )

    operacoes = [
        no("dec-1", TipoNo.DECISION),
        aresta("sess-1", "dec-1", TipoAresta.PRODUZ),
        no("apr-1", TipoNo.APRENDIZADO),
        aresta("sess-1", "apr-1", TipoAresta.PRODUZ),
        aresta("apr-1", "dec-1", TipoAresta.DERIVA_DE),
        aresta("apr-1", "proj-1", TipoAresta.VALE_PARA),
    ]
    with SQLiteEventStore(str(diretorio_dados / "graphow" / "graphow.db")) as store:
        recibo = WriteKernel(store).submeter_patch(
            PropostaPatch.criar(DadosPropostaPatch("david", PapelAutor.HUMANO, operacoes))
        )
    assert recibo.sucesso, recibo.mensagem


def test_notas_gerar_publica_o_acervo_e_confere_a_deriva_nominal(tmp_path: Path) -> None:
    """O acervo é projeção: gerado do grafo, conferido contra ele, e a edição à mão é deriva."""
    _criar_sessao_no_banco(tmp_path)
    _registrar_aprendizado_promovido_no_banco(tmp_path)
    destino = tmp_path / "acervo"

    codigo, console = _executar(["notas-gerar", "--destino", str(destino)], tmp_path)

    assert codigo == CODIGO_SUCESSO
    assert any("2 notas geradas" in linha for linha in console.linhas)
    assert (destino / "apr-1.md").is_file()
    assert (destino / "INDEX.md").is_file()
    assert _executar(["notas-gerar", "--destino", str(destino), "--conferir"], tmp_path)[0] == CODIGO_SUCESSO

    (destino / "apr-1.md").write_text("editado a mao", encoding="utf-8")

    codigo_deriva, console_deriva = _executar(["notas-gerar", "--destino", str(destino), "--conferir"], tmp_path)
    assert codigo_deriva == 1
    assert any("apr-1.md" in linha for linha in console_deriva.linhas)


def _popular(store: SQLiteEventStore) -> None:
    """Grava três eventos mínimos no repositório informado."""
    from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
    from graphow.core.types import OrigemEvento, PapelAutor

    for seq in range(1, 4):
        store.append_evento(
            EventoLog.criar(
                DadosCriacaoEvento(
                    seq=seq,
                    autor="david",
                    papel=PapelAutor.HUMANO,
                    tipo_evento=TipoEvento.NO_CRIADO,
                    payload={"id": f"n{seq}", "tipo": "Note", "rotulo": f"Nota {seq}"},
                    origem=OrigemEvento.HUMANO,
                )
            )
        )


def test_harness_de_inicio_imprime_a_vista_de_retomada_nominal(tmp_path: Path) -> None:
    """O que o hook de início imprime vira contexto do agente: a memória vai junto do recibo."""
    repositorio = tmp_path / "meu-repo"
    (repositorio / ".git").mkdir(parents=True)
    payload = json.dumps({"session_id": "sess-do-hook", "cwd": str(repositorio), "source": "startup"})

    codigo, console = _executar_com_payload(["harness", "--fase", "inicio", "--entrada-hook"], tmp_path, payload)

    assert codigo == CODIGO_SUCESSO
    assert any(linha.startswith("## Memoria do graphow") for linha in console.linhas)
    assert any("Protocolo de memoria do graphow" in linha for linha in console.linhas)
    assert any("`ler_vista` na sessao sess-do-hook" in linha for linha in console.linhas)


def test_harness_de_fim_nao_imprime_a_vista_edge_case(tmp_path: Path) -> None:
    """Caso de borda: no fim ninguém está lendo; a vista é do início."""
    _criar_sessao_no_banco(tmp_path)

    _, console = _executar(["harness", "--fase", "fim", "--sessao", "sess-1"], tmp_path)

    assert not any("Protocolo de memoria" in linha for linha in console.linhas)


def test_skill_instalar_copia_a_skill_do_repositorio_para_o_destino_nominal(tmp_path: Path) -> None:
    """Sem --origem, a skill vem do checkout em que o pacote foi instalado; --destino diz onde todo projeto a vê."""
    destino = tmp_path / "skills"

    codigo, console = _executar(["skill-instalar", "--destino", str(destino)], tmp_path)

    assert codigo == CODIGO_SUCESSO
    assert any("Skill graphow-mcp instalada em" in linha for linha in console.linhas)
    assert (destino / "graphow-mcp" / "SKILL.md").is_file()
    assert (destino / "graphow-mcp" / "references" / "patch_cookbook.md").is_file()


def test_skill_instalar_com_origem_sem_skill_recusa_edge_case(tmp_path: Path) -> None:
    """Caso de borda: origem errada é recusa explícita com o caminho, não traceback."""
    codigo, console = _executar(
        ["skill-instalar", "--origem", str(tmp_path / "nada"), "--destino", str(tmp_path / "skills")], tmp_path
    )

    assert codigo == 1
    assert any(linha.startswith("ERRO") and "--origem" in linha for linha in console.linhas)


def test_comando_mcp_sem_console_injetado_escreve_diagnostico_na_saida_de_erro_nominal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A saída padrão do `graphow mcp` é o canal JSON-RPC: "Banco: ..." ali quebrava o aperto de mão."""
    from graphow.api.cli_execucao import escolher_console

    saida, erro = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", saida)
    monkeypatch.setattr("sys.stderr", erro)

    escolher_console("mcp", None).escrever_linha("Banco: x.db")
    escolher_console("banco-info", None).escrever_linha("Banco de eventos: x.db")

    assert "Banco: x.db" in erro.getvalue()
    assert "Banco: x.db" not in saida.getvalue()
    assert "Banco de eventos: x.db" in saida.getvalue()


def test_console_injetado_vale_ate_para_o_comando_mcp_edge_case() -> None:
    """Caso de borda: o teste que injeta o console continua lendo o que o comando escreveu."""
    from graphow.api.cli_execucao import escolher_console

    injetado = EscritorConsoleEmMemoria()

    assert escolher_console("mcp", injetado) is injetado


def _transcricao(caminho: Path, id_task: str = "") -> None:
    """Duas respostas do modelo, a primeira repetida por bloco; a segunda assume a tarefa se houver."""
    uso = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 1}
    chamada = [{"type": "tool_use", "name": "mcp__graphow-executor__assumir_tarefa", "input": {"id_task": id_task}}]
    linhas = [
        {"type": "assistant", "message": {"id": "m1", "model": "claude-sonnet-5", "usage": uso, "content": []}},
        {"type": "assistant", "message": {"id": "m1", "model": "claude-sonnet-5", "usage": uso, "content": []}},
        {"type": "assistant", "message": {"id": "m2", "model": "claude-sonnet-5", "usage": uso, "content": chamada if id_task else []}},
    ]
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(json.dumps(linha) for linha in linhas) + "\n", encoding="utf-8")


def _run(tmp_path: Path, id_run: str):  # type: ignore[no-untyped-def]
    """O nó Run gravado no banco do teste, com as arestas que o penduram."""
    from graphow.kernel.write_kernel import WriteKernel

    with SQLiteEventStore(str(tmp_path / "graphow" / "graphow.db")) as store:
        view = WriteKernel(store).obter_view()
    return view.obter_no(id_run), view


def test_fim_grava_no_run_os_tokens_da_transcricao_da_sessao_nominal(tmp_path: Path) -> None:
    """O Run da sessão passa a dizer quanto o orquestrador gastou e que modelo de fato respondeu."""
    repositorio = tmp_path / "repo"
    (repositorio / ".git").mkdir(parents=True)
    transcricao = tmp_path / "projetos" / "sess-1.jsonl"
    _transcricao(transcricao)
    inicio = json.dumps({"session_id": "sess-1", "cwd": str(repositorio), "model": "claude-opus-5"})
    fim = json.dumps({"session_id": "sess-1", "cwd": str(repositorio), "transcript_path": str(transcricao), "reason": "clear"})

    _executar_com_payload(["harness", "--fase", "inicio", "--entrada-hook"], tmp_path, inicio)
    codigo, _ = _executar_com_payload(["harness", "--fase", "fim", "--entrada-hook"], tmp_path, fim)

    assert codigo == CODIGO_SUCESSO
    run, _ = _run(tmp_path, "run-sess-1")
    assert run.obter_propriedade("tokens_entrada") == 20
    assert run.obter_propriedade("tokens_cache_leitura") == 200
    assert run.obter_propriedade("mensagens_de_modelo") == 2
    assert run.obter_propriedade("modelo") == "claude-sonnet-5"
    assert run.obter_propriedade("modelos_usados") == ["claude-sonnet-5"]


def test_subagente_vira_run_proprio_pendurado_na_sessao_nominal(tmp_path: Path) -> None:
    """O fim de um subagente grava o que ele gastou e a tarefa que assumiu, na sessão que o despachou."""
    from graphow.core.types import TipoAresta

    repositorio = tmp_path / "repo"
    (repositorio / ".git").mkdir(parents=True)
    principal = tmp_path / "projetos" / "sess-1.jsonl"
    _transcricao(tmp_path / "projetos" / "sess-1" / "subagents" / "agent-ab12.jsonl", id_task="task-7")
    inicio = json.dumps({"session_id": "sess-1", "cwd": str(repositorio)})
    parada = json.dumps({
        "session_id": "sess-1", "cwd": str(repositorio), "transcript_path": str(principal),
        "agent_id": "ab12", "agent_type": "graphow-executor", "hook_event_name": "SubagentStop",
    })

    _executar_com_payload(["harness", "--fase", "inicio", "--entrada-hook"], tmp_path, inicio)
    codigo, console = _executar_com_payload(["harness", "--fase", "subagente", "--entrada-hook"], tmp_path, parada)

    assert codigo == CODIGO_SUCESSO
    assert any("run-sess-1-ab12" in linha for linha in console.linhas)
    run, view = _run(tmp_path, "run-sess-1-ab12")
    assert run.rotulo == "Subagente graphow-executor"
    assert run.obter_propriedade("agente") == "graphow-executor"
    assert run.obter_propriedade("modelo") == "claude-sonnet-5"
    assert run.obter_propriedade("tarefas") == ["task-7"]
    assert run.obter_propriedade("tokens_saida") == 10
    assert [a.origem_id for a in view.obter_arestas_entrada("run-sess-1-ab12", TipoAresta.PRODUZ)] == ["sess-1"]
    assert view.obter_no("sess-1").obter_propriedade("status") == "ativa"


def test_subagente_sem_transcricao_legivel_fica_sem_tokens_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem a transcrição, o Run nasce com quem foi o subagente e sem número inventado."""
    parada = json.dumps({"session_id": "sess-1", "agent_id": "zz99", "agent_type": "Explore"})

    codigo, _ = _executar_com_payload(["harness", "--fase", "subagente", "--entrada-hook"], tmp_path, parada)

    assert codigo == CODIGO_SUCESSO
    run, _ = _run(tmp_path, "run-sess-1-zz99")
    assert run.obter_propriedade("agente") == "Explore"
    assert run.obter_propriedade("tokens_entrada") is None


def test_orquestracao_medir_sem_goal_orquestrado_diz_que_nao_ha_o_que_medir_edge_case(tmp_path: Path) -> None:
    """Caso de borda: banco sem Goal decomposto responde em uma linha, sem traceback."""
    codigo, console = _executar(["orquestracao-medir"], tmp_path)

    assert codigo == CODIGO_SUCESSO
    assert any("nada a medir" in linha for linha in console.linhas)


def test_orquestracao_medir_aceita_varios_goals_nominal() -> None:
    """`--goal` se repete para comparar os Goals de uma rodada de configurações."""
    parsed = construir_parser().parse_args(["orquestracao-medir", "--goal", "goal-a", "--goal", "goal-b"])

    assert parsed.goal == ["goal-a", "goal-b"]
    assert parsed.ramo == "main"
