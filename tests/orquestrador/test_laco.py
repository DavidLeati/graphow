"""O laço do orquestrador de ponta a ponta, com um `claude -p` falso que responde por papel num repositório de brinquedo."""

import copy
from pathlib import Path

import pytest

from graphow.core.types import PapelAutor
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco, Parada
from graphow.orquestrador.git_do_goal import GitDoGoal
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.status import formatar_status

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import (
    PLANO,
    SOMA_CERTA,
    VERIFICAR,
    Bancada,
    ExecutorQueCai,
    Queda,
    autor_de_aceite,
    executor_pronto,
    montar_bancada,
    roteiro_completo,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")


@pytest.fixture(scope="module")
def completo(tmp_path_factory: pytest.TempPathFactory) -> tuple[Bancada, Parada]:
    """Uma corrida inteira no modo autônomo, compartilhada pelos testes que só a leem."""
    bancada = montar_bancada(tmp_path_factory.mktemp("completo"), roteiro_completo())
    return bancada, bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)


def _assuntos(repositorio: Path, ramo: str = "main") -> list[str]:
    """Os assuntos dos commits do ramo, do mais novo ao mais antigo."""
    return git(repositorio, "log", "--format=%s", ramo).splitlines()


def _autores_do_goal(bancada: Bancada) -> set[str]:
    """Os papéis que escreveram os eventos do grafo."""
    return {evento.papel.value for evento in bancada.kernel.repositorio.ler_eventos("main")}


def test_modo_autonomo_planeja_executa_corrige_verifica_e_integra_nominal(completo: tuple[Bancada, Parada]) -> None:
    """O laço inteiro: plano, duas fatias, bloqueante, correção, verificação limpa e fast-forward da main."""
    bancada, parada = completo

    assert parada.motivo == MotivoDaParada.FECHADO, parada.mensagem
    assert _assuntos(bancada.repositorio) == [
        "Registra as pendencias da verificacao 2 do Goal soma",
        "Fatia M1.K1.1: README sem exemplo (C2)",
        "Fatia F2: Uso no README (C2)",
        "Fatia F1: Funcao somar (C1)",
        "Escreve os testes de aceite do Goal soma (C1, C2)",
        "Planeja o Goal soma: Soma de dois numeros",
        "Estado inicial",
    ]
    assert (bancada.repositorio / "soma.py").read_text(encoding="utf-8") == SOMA_CERTA
    assert GitDoGoal(bancada.repositorio).mudancas() == ()
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.fechado and estado.rotulo == "Soma de dois numeros"
    assert [v.veredito for v in estado.verificacoes] == ["rejeitado", "aprovado"]
    assert estado.verificacoes[-1].commit == git(bancada.repositorio, "rev-parse", "HEAD~1").strip()
    assert [p["titulo"] for p in estado.pendencias] == ["nome do modulo"]
    assert "nome do modulo" in (bancada.repositorio / "docs" / "goals" / "soma.md").read_text(encoding="utf-8")
    assert _autores_do_goal(bancada) == {PapelAutor.ORQUESTRADOR.value}


def test_sessoes_rodam_sem_mcp_com_schema_prompt_do_pacote_e_git_travado_nominal(completo: tuple[Bancada, Parada]) -> None:
    """F1.2 e F1.4: cada sessão sem MCP nem configuração do usuário, com schema, prompt do pacote e a trava do git."""
    bancada, _ = completo

    chamadas = bancada.chamadas()

    assert [c["papel"] for c in chamadas] == ["planejador", "aceite", "executor", "executor", "verificador", "executor", "verificador"]
    for chamada in chamadas:
        argv = chamada["argv"]
        assert "--strict-mcp-config" in argv and "--json-schema" in argv
        assert argv[argv.index("--setting-sources") + 1] == "project"
        assert Path(argv[argv.index("--append-system-prompt-file") + 1]).parent.name == "prompts"
        assert "Bash(git commit:*)" in argv
        assert chamada["ambiente"]["GIT_CONFIG_KEY_0"] == "core.hooksPath"
        assert chamada["tem_claude"] is False
        assert "mcp__graphow" not in " ".join(argv)
    executor = chamadas[2]["argv"]
    assert executor[executor.index("--tools") + 1] == "Bash,Read,Edit,Write,Glob,Grep"
    assert "Edit" not in chamadas[4]["argv"][chamadas[4]["argv"].index("--tools") + 1]


def test_briefing_do_executor_traz_criterios_decisoes_e_o_que_ja_foi_entregue_nominal(completo: tuple[Bancada, Parada]) -> None:
    """O briefing é montado por código, com o texto inteiro e os commits das fatias anteriores."""
    bancada, _ = completo

    segunda = bancada.chamadas("executor")[1]["stdin"]
    verificador = bancada.chamadas("verificador")[0]["stdin"]

    assert "# Fatia F2 do Goal goal-soma: F2: Uso no README" in segunda
    assert "- C2 (checagem): o README explica como usar somar" in segunda
    assert "- D1: so a biblioteca padrao Motivo: o repositorio nao tem dependencias" in segunda
    assert "Fatia F1: Funcao somar (C1)" in segunda
    assert "Quero somar dois numeros." in segunda
    assert "feito" not in verificador.split("## Spec completa")[0]


def test_telemetria_registra_cada_sessao_com_custo_fora_do_grafo_nominal(completo: tuple[Bancada, Parada]) -> None:
    """F1.5: uma linha por invocação, com papel, fatia, sessão e custo; nenhum Run no grafo."""
    bancada, _ = completo

    registros = bancada.telemetria.listar("goal-soma")
    totais = bancada.telemetria.totais("goal-soma")
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")

    assert [r.papel for r in registros] == ["planejador", "aceite", "executor", "executor", "verificador", "executor", "verificador"]
    assert registros[2].fatia == "task-soma-f1" and registros[2].session_id
    assert round(totais.custo_usd, 2) == 2.50
    assert not [no for no in bancada.kernel.obter_view().listar_todos_os_nos() if no.tipo.value == "Run"]
    assert estado is not None
    linhas = "\n".join(formatar_status(estado, registros))
    assert "Sessoes: 7 invocacao(oes) em 7 sessao(oes) | US$ 2.50" in linhas


def test_modo_supervisionado_para_no_plano_e_no_pronto_para_integrar_nominal(tmp_path: Path) -> None:
    """Para no portão do plano; aprovado, executa; limpo, espera o humano integrar; integrado, fecha."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("atende")]
    roteiro["executor"] = roteiro["executor"][:2]
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()

    no_plano = orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco())
    sem_aprovacao = orquestrador.rodar("goal-soma", OpcoesDoLaco())
    orquestrador.aprovar_plano("goal-soma", "david")
    pronto = orquestrador.rodar("goal-soma", OpcoesDoLaco())
    git(bancada.repositorio, "merge", "-q", "--ff-only", "graphow/soma")
    fechado = orquestrador.rodar("goal-soma", OpcoesDoLaco())

    assert no_plano.motivo == sem_aprovacao.motivo == MotivoDaParada.AGUARDANDO_APROVACAO
    assert "--aprovar-plano" in no_plano.mensagem
    assert pronto.motivo == MotivoDaParada.PRONTO_PARA_INTEGRAR
    assert fechado.motivo == MotivoDaParada.FECHADO
    assert len(bancada.chamadas("executor")) == 2
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.configuracao is not None and estado.configuracao.modo == "supervisionado"


def test_queda_no_meio_da_fatia_retoma_com_nova_tentativa_nominal(tmp_path: Path) -> None:
    """O processo cai durante a sessão de F1; rodar de novo descarta o que ficou e refaz a fatia."""
    roteiro = roteiro_completo()
    roteiro["executor"].insert(0, executor_pronto({"soma.py": "def somar(a, b):\n    return a - b\n", "lixo.txt": "x"}))
    bancada = montar_bancada(tmp_path, roteiro)

    with pytest.raises(Queda):
        bancada.orquestrador(executor=ExecutorQueCai(bancada.executor, 3)).iniciar_da_spec(
            bancada.spec, bancada.repositorio, AUTONOMO
        )
    parada = bancada.orquestrador().rodar("goal-soma", AUTONOMO)

    assert parada.motivo == MotivoDaParada.FECHADO, parada.mensagem
    assert not (bancada.repositorio / "lixo.txt").exists()
    assert "foi interrompida" in bancada.chamadas("executor")[1]["stdin"]
    assert list((tmp_path / "estado" / "goal-soma" / "patches").glob("task-soma-f1-t1-interrompida.patch"))
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.fatias[0].tentativas == 2


def test_duvida_pausa_so_a_fatia_e_a_resposta_volta_no_briefing_nominal(tmp_path: Path) -> None:
    """F1 pergunta; F2, que não depende dela, segue; o laço espera o humano e retoma com a resposta."""
    plano = copy.deepcopy(PLANO)
    plano["fatias"][1]["depende_de"] = []
    roteiro = roteiro_completo()
    roteiro["planejador"] = [{"saida": plano, "custo": 0.4}]
    duvida = {"saida": {"status": "duvida", "resumo": "parei", "arquivos": [], "testes": [], "duvida": "Inteiros ou decimais?"},
              "arquivos": {"rascunho.py": "x = 1\n"}, "custo": 0.1}
    roteiro["executor"] = [duvida, roteiro["executor"][1], roteiro["executor"][0], roteiro["executor"][2]]
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()

    pausado = orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    ultimo_antes_da_resposta = _assuntos(bancada.repositorio, "graphow/soma")[0]
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    id_questao = estado.fatias[0].duvidas[0].id
    resposta = PropostaPatch.criar(DadosPropostaPatch(
        autor="david", papel=PapelAutor.HUMANO, justificativa="resposta",
        operacoes=(ItemPatch(OperacaoPatch.REPLACE, f"/nos/{id_questao}/propriedades/status", "respondida"),
                   ItemPatch(OperacaoPatch.REPLACE, f"/nos/{id_questao}/propriedades/resposta", "So inteiros")),
    ))
    assert bancada.kernel.submeter_patch(resposta).sucesso
    fechado = orquestrador.rodar("goal-soma", AUTONOMO)

    assert pausado.motivo == MotivoDaParada.AGUARDANDO_RESPOSTA
    assert "Inteiros ou decimais?" in pausado.mensagem
    assert ultimo_antes_da_resposta == "Fatia F2: Uso no README (C2)"
    assert "Resposta: So inteiros" in bancada.chamadas("executor")[2]["stdin"]
    assert "tentativa pausada tinha mudado" in bancada.chamadas("executor")[2]["stdin"]
    assert not (bancada.repositorio / "rascunho.py").exists()
    assert fechado.motivo == MotivoDaParada.FECHADO, fechado.mensagem


def test_saida_invalida_volta_a_mesma_sessao_uma_vez_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o executor devolve status fora do schema; a mesma sessão é retomada com o erro e corrige."""
    roteiro = roteiro_completo()
    invalida = {"saida": {"status": "talvez", "resumo": "?", "arquivos": [], "testes": [], "duvida": ""}, "custo": 0.1}
    roteiro["executor"].insert(0, invalida)
    roteiro["executor"][1]["custo"] = 0.2
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    primeira, retomada = bancada.chamadas("executor")[:2]
    assert parada.fechou, parada.mensagem
    assert "--resume" not in primeira["argv"]
    assert "--resume" in retomada["argv"]
    assert "nao conferiu" in retomada["stdin"] and "talvez" in retomada["stdin"]
    registros = bancada.telemetria.listar("goal-soma")
    assert [r.retomada for r in registros if r.fatia == "task-soma-f1"] == [False, True]
    assert round(bancada.telemetria.totais("goal-soma").custo_usd, 2) == 2.50


def test_duas_falhas_viram_pendencia_e_o_laco_para_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a suíte fica vermelha duas vezes; a fatia vira pendência com o erro e o laço para."""
    roteiro = roteiro_completo()
    errada = executor_pronto({"soma.py": "def somar(a, b):\n    return 1\n", "verificar.py": VERIFICAR})
    roteiro["executor"] = [errada, copy.deepcopy(errada)]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.PENDENCIA
    assert "AssertionError" in bancada.chamadas("executor")[1]["stdin"]
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and [f.codigo for f in estado.bloqueadas()] == ["F1"]
    assert _assuntos(bancada.repositorio, "graphow/soma")[0].startswith("Escreve os testes de aceite")
    assert GitDoGoal(Path(estado.configuracao.area)).mudancas() == ()


def test_orcamento_estourado_para_antes_da_sessao_seguinte_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o plano custou mais que o orçamento; nenhum executor abre."""
    roteiro = roteiro_completo()
    roteiro["planejador"][0]["custo"] = 5.0
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco(modo="autonomo", orcamento_usd=4.0))

    assert parada.motivo == MotivoDaParada.ORCAMENTO
    assert "US$ 5.00 de US$ 4.00" in parada.mensagem
    assert bancada.chamadas("executor") == []
    planejador = bancada.chamadas("planejador")[0]["argv"]
    assert planejador[planejador.index("--max-budget-usd") + 1] == "4.00"


def test_executor_que_tenta_commitar_nao_consegue_e_o_orquestrador_commita_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o `git commit` do executor bate na trava; o que escapa por -c é desfeito; o commit é do orquestrador."""
    roteiro = roteiro_completo()
    vazia = str(tmp_path / "sem-hooks")
    roteiro["executor"][0]["comandos"] = [
        ["git", "add", "-A"],
        ["git", "commit", "-q", "--no-verify", "-m", "commit do executor"],
        ["git", "-c", f"core.hooksPath={vazia}", "commit", "-q", "-m", "commit que escapou"],
    ]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    comandos = bancada.chamadas("executor")[0]["comandos"]
    assert comandos[1]["codigo"] != 0 and "quem commita e o orquestrador" in comandos[1]["erro"]
    assert parada.fechou, parada.mensagem
    assuntos = _assuntos(bancada.repositorio)
    assert "commit do executor" not in assuntos and "commit que escapou" not in assuntos
    assert "Fatia F1: Funcao somar (C1)" in assuntos
    artefato = bancada.kernel.obter_view().obter_no("art-task-soma-f1-t1")
    assert artefato is not None
    assert comandos[2]["codigo"] == 0, "o -c core.hooksPath passa por cima da trava do ambiente"
    assert "o commit foi desfeito com reset --soft" in str(artefato.obter_propriedade("observacao"))


def _goal_do_gerente(bancada: Bancada, *, criterio: str = "Constraint") -> None:
    """O Goal como o gerente grava: Sessao do humano, critério (Criterio, ou a Constraint de antes) e decisão com motivo."""
    def no(id_no: str, tipo_no: str, rotulo: str, **propriedades: object) -> ItemPatch:
        return ItemPatch(OperacaoPatch.ADD, f"/nos/{id_no}", {"id": id_no, "tipo": tipo_no, "rotulo": rotulo, "propriedades": propriedades})

    def aresta(origem: str, destino: str, tipo: str) -> ItemPatch:
        return ItemPatch(OperacaoPatch.ADD, f"/arestas/{tipo}-{origem}-{destino}",
                         {"id": f"{tipo}-{origem}-{destino}", "origem_id": origem, "destino_id": destino, "tipo": tipo})

    operacoes = (
        no("proj", "Projeto", "Brinquedo"), no("setor", "Setor", "Demandas"), aresta("proj", "setor", "contem"),
        no("sess", "Sessao", "Gerente"), aresta("setor", "sess", "contem"),
        no("goal-calc", "Goal", "Somar", descricao="O time quer somar dois inteiros."), aresta("sess", "goal-calc", "produz"),
        no("crit-calc-1", criterio, "somar(2, 3) devolve 5", tipo="criterio_aceite")
        if criterio == "Constraint" else
        no("crit-calc-1", criterio, "C1: somar(2, 3) devolve 5", codigo="C1", texto="somar(2, 3) devolve 5", verificacao="checagem"),
        aresta("sess", "crit-calc-1", "produz"), aresta("crit-calc-1", "goal-calc", "escopa"),
        no("dec-calc-1", "Decision", "so a biblioteca padrao", motivo="o repositorio nao tem dependencias"),
        aresta("sess", "dec-calc-1", "produz"), aresta("dec-calc-1", "goal-calc", "orienta"),
    )
    proposta = PropostaPatch.criar(DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="gerente"))
    assert bancada.kernel.submeter_patch(proposta).sucesso


def test_goal_do_gerente_vira_spec_com_texto_inteiro_e_mantem_os_nos_fixados_nominal(tmp_path: Path) -> None:
    """`--goal`: a spec sai dos nós com o texto inteiro, e o plano reaproveita o critério e a decisão do humano."""
    bancada = montar_bancada(tmp_path, roteiro_completo())
    _goal_do_gerente(bancada)

    parada = bancada.orquestrador().rodar("goal-calc", AUTONOMO, bancada.repositorio)

    briefing = bancada.chamadas("planejador")[0]["stdin"]
    assert "- C1 (crit-calc-1, teste): somar(2, 3) devolve 5" in briefing
    assert "- D1 (dec-calc-1): so a biblioteca padrao Motivo: o repositorio nao tem dependencias" in briefing
    assert "ja foram fixados pelo humano" in briefing
    assert parada.fechou, parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-calc")
    assert estado is not None and estado.plano is not None
    assert [c["no"] for c in estado.plano["criterios"]] == ["crit-calc-1", "crit-calc-c2"]
    assert [d["no"] for d in estado.plano["decisoes"]] == ["dec-calc-1"]
    assert estado.rotulo == "Somar"


def test_goal_do_gerente_com_criterio_como_no_usa_o_texto_e_a_verificacao_do_humano_nominal(tmp_path: Path) -> None:
    """F2.6: o Criterio do gerente vale como ele o escreveu; o planejador que o reescreve não muda o nó nem o plano."""
    roteiro = roteiro_completo()
    roteiro["planejador"][0]["saida"]["criterios"][0]["texto"] = "somar devolve a soma"
    so_checagem = autor_de_aceite()
    for item in so_checagem["saida"]["criterios"]:
        item["testes"], item["checagem"] = [], ["abrir o arquivo e conferir"]
    roteiro["aceite"] = [so_checagem]
    bancada = montar_bancada(tmp_path, roteiro)
    _goal_do_gerente(bancada, criterio="Criterio")

    parada = bancada.orquestrador().rodar("goal-calc", AUTONOMO, bancada.repositorio)

    assert "- C1 (crit-calc-1, checagem): somar(2, 3) devolve 5" in bancada.chamadas("planejador")[0]["stdin"]
    assert parada.fechou, parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-calc")
    assert estado is not None and estado.plano is not None
    assert estado.plano["criterios"][0] == {"id": "C1", "texto": "somar(2, 3) devolve 5", "verificacao": "checagem", "no": "crit-calc-1"}
    no = bancada.kernel.obter_view().obter_no("crit-calc-1")
    assert no is not None and no.obter_propriedade("texto") == "somar(2, 3) devolve 5"
    assert no.obter_propriedade("estado") == "atende", "o estado do Criterio do humano vem das verificacoes"
    novo = bancada.kernel.obter_view().obter_no("crit-calc-c2")
    assert novo is not None and novo.tipo.value == "Criterio" and novo.obter_propriedade("estado") == "atende"


def test_goal_do_gerente_sem_repositorio_e_recusado_edge_case(tmp_path: Path) -> None:
    """Caso de borda: na primeira vez o Goal do gerente precisa dizer em que repositório o trabalho acontece."""
    bancada = montar_bancada(tmp_path, roteiro_completo())
    _goal_do_gerente(bancada)

    parada = bancada.orquestrador().rodar("goal-calc", AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA
    assert "PedidoInvalido" in parada.mensagem and "--repo" in parada.mensagem


def test_goal_com_plano_aprovado_pelo_escopo_governado_segue_o_portao_do_orquestrador_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o `aprovar_plano` antigo do escopo não aprova o plano do orquestrador nem barra as fatias dele."""
    from graphow.mcp.ferramentas_escopo import FerramentasEscopo
    from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
    from graphow.mcp.submissao import ContextoFerramentaMCP

    bancada = montar_bancada(tmp_path, roteiro_completo())
    _goal_do_gerente(bancada)
    antigo = FerramentasEscopo(ContextoFerramentaMCP(bancada.kernel, IdentidadeSessaoMCP.criar("david", "humano")))
    assert antigo.aprovar_plano({"id_goal": "goal-calc"})["sucesso"]
    orquestrador = bancada.orquestrador()

    no_portao = orquestrador.rodar("goal-calc", OpcoesDoLaco(), bancada.repositorio)
    orquestrador.aprovar_plano("goal-calc", "david")
    fechado = orquestrador.rodar("goal-calc", OpcoesDoLaco(modo="autonomo"))

    assert no_portao.motivo == MotivoDaParada.AGUARDANDO_APROVACAO, no_portao.mensagem
    assert fechado.fechou, fechado.mensagem
    assert len(bancada.chamadas("planejador")) == 1
