"""Testes da seção Governanca: a vista de Sessao, Task e Goal diz a política efetiva do Projeto do alvo."""

from typing import Any

from graphow.context.governanca_vigente import (
    TITULO_DA_SECAO_DE_GOVERNANCA,
    descrever_governanca,
    gestos_com_o_arbitro,
    nome_do_preset,
    resolver_politica_na_vista,
)
from graphow.context.materializer import MaterializadorContexto, RequisicaoVista
from graphow.core.governanca import Gesto, compor_politica_global, politica_do_preset, PresetGovernanca
from graphow.core.models import GrafoEstado, NoGrafo
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.kernel.politica_governanca import resolver_politica_do_no
from graphow.kernel.rastreio_projeto import RastreadorProjetoAncestral
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.server import GraphowMCPServer
from graphow.projection.graph_view import GrafoView

ORCAMENTO: int = 3000
CABECALHO: str = f"## {TITULO_DA_SECAO_DE_GOVERNANCA}"
LINHA_DA_GOVERNANCA_MAXIMA: str = "- governanca_maxima: todos os gestos com o humano"


def _no(id_no: str, tipo: TipoNo, rotulo: str, **propriedades: Any) -> ItemPatch:
    """Operação de criação de nó com propriedades opcionais."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{id_no}",
        value={"id": id_no, "tipo": tipo.value, "rotulo": rotulo, "propriedades": dict(propriedades)},
    )


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Operação de criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value},
    )


def _projeto(sufixo: str, **propriedades: Any) -> list[ItemPatch]:
    """Projeto, Setor, Sessao, Task e Goal ligados, com as propriedades dadas no Projeto."""
    return [
        _no(f"proj-{sufixo}", TipoNo.PROJETO, f"Projeto {sufixo}", **propriedades),
        _no(f"setor-{sufixo}", TipoNo.SETOR, f"Setor {sufixo}"),
        _aresta(f"proj-{sufixo}", f"setor-{sufixo}", TipoAresta.CONTEM),
        _no(f"sess-{sufixo}", TipoNo.SESSAO, f"Sessao {sufixo}", status="ativa"),
        _aresta(f"setor-{sufixo}", f"sess-{sufixo}", TipoAresta.CONTEM),
        _no(f"task-{sufixo}", TipoNo.TASK, f"Tarefa {sufixo}", status="pendente"),
        _aresta(f"sess-{sufixo}", f"task-{sufixo}", TipoAresta.PRODUZ),
        _no(f"goal-{sufixo}", TipoNo.GOAL, f"Objetivo {sufixo}"),
        _aresta(f"sess-{sufixo}", f"goal-{sufixo}", TipoAresta.PRODUZ),
        _no(f"duv-{sufixo}", TipoNo.QUESTION, f"Duvida {sufixo}", status="aberta"),
        _aresta(f"sess-{sufixo}", f"duv-{sufixo}", TipoAresta.PRODUZ),
        _aresta(f"duv-{sufixo}", f"task-{sufixo}", TipoAresta.BLOQUEIA),
    ]


def _submeter(kernel: WriteKernel, operacoes: list[ItemPatch]) -> None:
    """Submete o lote como humano, exigindo aceitação."""
    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="cenario")
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))
    assert recibo.sucesso, recibo.mensagem


def _kernel(*lotes: list[ItemPatch]) -> WriteKernel:
    """Kernel em memória com os lotes submetidos em ordem."""
    kernel = montar_kernel_em_memoria()
    for lote in lotes:
        _submeter(kernel, lote)
    return kernel


def _configurar_global(kernel: WriteKernel, argumentos: dict[str, Any]) -> None:
    """O humano grava a política global pela ferramenta."""
    servidor = GraphowMCPServer(kernel, IdentidadeSessaoMCP.criar("david", "humano"))
    resposta = servidor.executar_ferramenta("configurar_governanca", {"escopo": "global", **argumentos})
    assert resposta["sucesso"] is True, resposta


def _vista(kernel: WriteKernel, id_alvo: str, orcamento: int = ORCAMENTO, papel: PapelAutor = PapelAutor.EXECUTOR) -> str:
    """Materializa a vista do alvo sob o papel e o orçamento informados."""
    requisicao = RequisicaoVista(id_alvo=id_alvo, papel=papel, orcamento_tokens=orcamento)
    return MaterializadorContexto().materializar(requisicao, kernel.obter_view()).conteudo_formatado


def _secao(conteudo: str) -> list[str]:
    """As linhas da seção Governanca, sem o cabeçalho; vazia se a vista não a traz."""
    linhas = conteudo.splitlines()
    if CABECALHO not in linhas:
        return []
    resto = linhas[linhas.index(CABECALHO) + 1 :]
    return resto[: resto.index("")] if "" in resto else resto


def test_governanca_maxima_sem_legado_e_uma_linha_so_nominal() -> None:
    """Sem configuração nenhuma, Sessao, Task e Goal dizem numa linha que tudo é do humano."""
    kernel = _kernel(_projeto("a"))

    for id_alvo in ("sess-a", "task-a", "goal-a"):
        assert _secao(_vista(kernel, id_alvo)) == [LINHA_DA_GOVERNANCA_MAXIMA], id_alvo


def test_arbitragem_maxima_lista_os_gestos_com_o_arbitro_nominal() -> None:
    """O Projeto em arbitragem_maxima diz o preset, os gestos do árbitro e o que segue humano."""
    kernel = _kernel(_projeto("a", governanca={"preset": "arbitragem_maxima"}))

    for id_alvo in ("sess-a", "task-a", "goal-a"):
        secao = "\n".join(_secao(_vista(kernel, id_alvo)))
        assert "preset efetivo: arbitragem_maxima" in secao, id_alvo
        for gesto in ("responder_questao", "promover_aprendizado", "encerrar_sessao", "integracao"):
            assert gesto in secao, (id_alvo, gesto)
        assert "estrutura ilimitada" in secao
        assert "promocao global" in secao
        assert "configuracao da governanca" in secao


def test_personalizada_do_projeto_so_cita_o_que_saiu_do_humano_nominal() -> None:
    """Na personalizada aparecem só os gestos entregues ao árbitro e o teto de correções fora do padrão."""
    kernel = _kernel(
        _projeto("a", governanca={"preset": "personalizada", "personalizada": {"excluir": "arbitro", "max_correcoes": 4}})
    )

    secao = "\n".join(_secao(_vista(kernel, "task-a")))

    assert "preset efetivo: personalizada" in secao
    assert "- com o arbitro: excluir" in secao
    assert "promover_aprendizado" not in secao
    assert "max_correcoes: 4" in secao
    assert "estrutura ilimitada" not in secao


def test_projeto_herda_a_politica_global_nominal() -> None:
    """Sem preset próprio, o Projeto vale a global, e a vista de outro Projeto diz o seu."""
    kernel = _kernel(_projeto("a"), _projeto("b", governanca={"preset": "governanca_maxima"}))
    _configurar_global(kernel, {"preset": "arbitragem_maxima"})

    herdado = "\n".join(_secao(_vista(kernel, "task-a")))
    proprio = _secao(_vista(kernel, "task-b"))

    assert "preset efetivo: arbitragem_maxima" in herdado
    assert proprio == [LINHA_DA_GOVERNANCA_MAXIMA]


def test_legado_nivel_autonomia_ilimitado_aparece_como_estrutura_nominal() -> None:
    """O Projeto legado em governança máxima não afirma que tudo é do humano: a estrutura é ilimitada."""
    kernel = _kernel(_projeto("a", nivel_autonomia="ilimitado"))

    secao = "\n".join(_secao(_vista(kernel, "task-a")))

    assert LINHA_DA_GOVERNANCA_MAXIMA not in secao
    assert "estrutura ilimitada (legado nivel_autonomia)" in secao
    assert "com o arbitro" not in secao


def test_a_secao_vale_para_todo_papel_que_le_nominal() -> None:
    """A política é do Projeto do alvo: planejador, revisor e árbitro leem a mesma coisa."""
    kernel = _kernel(_projeto("a", governanca={"preset": "arbitragem_maxima"}))

    secoes = {papel: _secao(_vista(kernel, "task-a", papel=papel)) for papel in PapelAutor if papel != PapelAutor.SISTEMA}

    assert secoes[PapelAutor.EXECUTOR]
    assert all(secao == secoes[PapelAutor.EXECUTOR] for secao in secoes.values())


def test_outros_tipos_de_alvo_nao_ganham_a_secao_edge_case() -> None:
    """Caso de borda: a Question e o Projeto não a trazem; o pedido era Sessao, Task e Goal."""
    kernel = _kernel(_projeto("a", governanca={"preset": "arbitragem_maxima"}))

    assert _secao(_vista(kernel, "duv-a")) == []
    assert _secao(_vista(kernel, "proj-a")) == []


def test_governanca_cai_antes_de_cortar_os_aprendizados_aplicaveis_edge_case() -> None:
    """Caso de borda: sob aperto a seção sai primeiro, e os Aprendizados Aplicaveis seguem na vista."""
    kernel = _kernel(
        _projeto("a", governanca={"preset": "arbitragem_maxima"}),
        [
            _no("apr-a", TipoNo.APRENDIZADO, "Medir o teto antes de mexer", como_aplicar="Meca primeiro"),
            _aresta("sess-a", "apr-a", TipoAresta.PRODUZ),
            _aresta("apr-a", "task-a", TipoAresta.DERIVA_DE),
            _aresta("apr-a", "proj-a", TipoAresta.VALE_PARA),
        ],
    )
    inteira = MaterializadorContexto().materializar(
        RequisicaoVista(id_alvo="task-a", papel=PapelAutor.EXECUTOR, orcamento_tokens=ORCAMENTO), kernel.obter_view()
    )

    apertada = _vista(kernel, "task-a", orcamento=inteira.tokens_estimados - 1)

    assert CABECALHO in inteira.conteudo_formatado
    assert CABECALHO not in apertada.splitlines()
    assert "## Aprendizados Aplicaveis" in apertada
    assert "[apr-a]" in apertada


def test_governanca_nao_entra_nos_ids_expansiveis_edge_case() -> None:
    """Caso de borda: a seção não cita nó nenhum, então não altera o que a vista anuncia como expansível."""
    kernel = _kernel(_projeto("a", governanca={"preset": "arbitragem_maxima"}))
    requisicao = RequisicaoVista(id_alvo="task-a", papel=PapelAutor.EXECUTOR, orcamento_tokens=ORCAMENTO)

    vista = MaterializadorContexto().materializar(requisicao, kernel.obter_view())

    assert TITULO_DA_SECAO_DE_GOVERNANCA not in vista.vizinhos_expansiveis
    assert CABECALHO in vista.conteudo_formatado


def test_resolucao_na_vista_acha_o_projeto_pela_hierarquia_nominal() -> None:
    """Task, Sessao e Goal resolvem o Projeto que os contém; um nó solto resolve a global."""
    kernel = _kernel(_projeto("a", governanca={"preset": "arbitragem_maxima"}))
    view = kernel.obter_view()

    for id_no in ("task-a", "sess-a", "goal-a", "duv-a", "proj-a"):
        assert nome_do_preset(resolver_politica_na_vista(id_no, view)) == "arbitragem_maxima", id_no
    assert nome_do_preset(resolver_politica_na_vista("inexistente", view)) == "governanca_maxima"


def test_no_sem_projeto_resolve_a_global_edge_case() -> None:
    """Caso de borda: fora de qualquer Projeto o nó vale a política global."""
    solto = NoGrafo("solto", TipoNo.TASK, "Solta")
    view = GrafoView(GrafoEstado(nos={"solto": solto}))

    assert nome_do_preset(resolver_politica_na_vista("solto", view)) == "governanca_maxima"


def test_nome_do_preset_e_gestos_do_arbitro_nominal() -> None:
    """O preset efetivo é o que os valores repetem; fora disso, personalizada."""
    arbitragem = politica_do_preset(PresetGovernanca.ARBITRAGEM_MAXIMA)
    parcial = compor_politica_global({"preset": "personalizada", "personalizada": {"fechar_goal": "arbitro"}})

    assert nome_do_preset(arbitragem) == "arbitragem_maxima"
    assert nome_do_preset(parcial) == "personalizada"
    assert gestos_com_o_arbitro(parcial) == (Gesto.FECHAR_GOAL,)
    assert descrever_governanca(parcial)[1] == "- com o arbitro: fechar_goal"


def _projeto_b_com_decisao() -> list[ItemPatch]:
    """Projeto B em arbitragem_maxima, com uma Decision produzida pela sessão dele; criado antes do A."""
    return [
        *_projeto("b", governanca={"preset": "arbitragem_maxima"}),
        _no("dec-b", TipoNo.DECISION, "Decisao do projeto B"),
        _aresta("sess-b", "dec-b", TipoAresta.PRODUZ),
    ]


def _projeto_a_com_task_sob_goal() -> list[ItemPatch]:
    """Projeto A em governanca_maxima, cuja Task desce de um Goal: o caminho até o Projeto tem quatro saltos."""
    return [
        *_projeto("a", governanca={"preset": "governanca_maxima"}),
        _no("task-a2", TipoNo.TASK, "Tarefa sob o Goal", status="pendente"),
        _aresta("goal-a", "task-a2", TipoAresta.DECOMPOE),
    ]


def test_vista_repete_o_veredito_do_kernel_com_orienta_de_outro_projeto_edge_case() -> None:
    """Caso de borda: Task de A orientada por Decision de B, os dois a quatro saltos; a contenção decide.

    Só `contem`, `produz` e `decompoe` dizem a que Projeto a Task pertence, então
    a Decision de B não puxa a política de B: a Task segue com a de A. A seção
    diz o que o RoleGate aplica, e não o que outra busca concluiria.
    """
    kernel = _kernel(
        _projeto_b_com_decisao(),
        _projeto_a_com_task_sob_goal(),
        [_aresta("dec-b", "task-a2", TipoAresta.ORIENTA)],
    )
    estado = kernel.obter_view().estado
    do_kernel = resolver_politica_do_no("task-a2", estado, RastreadorProjetoAncestral())

    secao = _secao(_vista(kernel, "task-a2"))

    assert RastreadorProjetoAncestral().rastrear("task-a2", estado) == "proj-a"
    assert nome_do_preset(do_kernel) == "governanca_maxima"
    assert secao == list(descrever_governanca(do_kernel))
    assert secao == [LINHA_DA_GOVERNANCA_MAXIMA]


def test_vista_de_task_sem_ambiguidade_diz_a_politica_do_seu_projeto_nominal() -> None:
    """Sem empate, a Task de A segue com a política de A, mesmo orientada por Decision de B."""
    kernel = _kernel(
        _projeto_b_com_decisao(),
        _projeto("a", governanca={"preset": "governanca_maxima"}),
        [_aresta("dec-b", "task-a", TipoAresta.ORIENTA)],
    )
    estado = kernel.obter_view().estado

    secao = _secao(_vista(kernel, "task-a"))

    assert RastreadorProjetoAncestral().rastrear("task-a", estado) == "proj-a"
    assert secao == [LINHA_DA_GOVERNANCA_MAXIMA]


def test_vista_diz_a_politica_restrita_quando_goal_de_outro_projeto_decompoe_a_task_edge_case() -> None:
    """Caso de borda: Goal de B (arbitragem) decompõe a Task de A (governanca_maxima); a seção diz a política restrita.

    O Projeto B não é o dono da Task. A vista repete a composição do kernel, e
    a Task segue toda com o humano.
    """
    kernel = _kernel(
        _projeto_b_com_decisao(),
        _projeto("a", governanca={"preset": "governanca_maxima"}),
        [_aresta("goal-b", "task-a", TipoAresta.DECOMPOE)],
    )
    estado = kernel.obter_view().estado
    do_kernel = resolver_politica_do_no("task-a", estado, RastreadorProjetoAncestral())

    secao = _secao(_vista(kernel, "task-a"))

    assert RastreadorProjetoAncestral().rastrear_todos("task-a", estado) == ("proj-a", "proj-b")
    assert not gestos_com_o_arbitro(do_kernel)
    assert secao == list(descrever_governanca(do_kernel))
    assert secao == [LINHA_DA_GOVERNANCA_MAXIMA]


def test_vista_de_projeto_permissivo_com_goal_restritivo_alheio_nao_entrega_ao_arbitro_edge_case() -> None:
    """Caso de borda: A em arbitragem e Goal de B em governanca_maxima: a Task de A deixa de ter gestos com o árbitro."""
    kernel = _kernel(
        _projeto("b", governanca={"preset": "governanca_maxima"}),
        _projeto("a", governanca={"preset": "arbitragem_maxima"}),
        [_aresta("goal-b", "task-a", TipoAresta.DECOMPOE)],
    )
    sozinho = _kernel(_projeto("a", governanca={"preset": "arbitragem_maxima"}))

    assert not gestos_com_o_arbitro(resolver_politica_na_vista("task-a", kernel.obter_view()))
    assert _secao(_vista(kernel, "task-a")) == [LINHA_DA_GOVERNANCA_MAXIMA]
    assert gestos_com_o_arbitro(resolver_politica_na_vista("task-a", sozinho.obter_view()))
