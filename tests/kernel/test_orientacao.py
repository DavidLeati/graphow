"""A decisão chega à Task em que vale, e a evidência aponta o trabalho que avalia.

A Decision tomada numa sessão posterior à da Task não tinha caminho até ela: a
vista do executor só a alcançava quando as duas nasciam na mesma sessão. E a
Evidence do teste ou da revisão ficava presa à sessão, sem apontar o Artifact.
"""

from graphow.context.materializer import MaterializadorContexto, RequisicaoVista
from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, object] | None = None) -> ItemPatch:
    """Criação de nó com rótulo igual ao id."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades or {}}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    valor = {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=valor)


def _submeter(kernel: WriteKernel, papel: PapelAutor, *operacoes: ItemPatch) -> ResultadoSubmissao:
    """Submete o lote sob o papel informado, com um autor por papel."""
    dados = DadosPropostaPatch(autor=f"autor-{papel.value}", papel=papel, operacoes=operacoes, justificativa="teste")
    return kernel.submeter_patch(PropostaPatch.criar(dados))


def _montar_duas_sessoes() -> WriteKernel:
    """A Task nasce na primeira sessão; a segunda sessão é a de quem decide depois."""
    kernel = montar_kernel_em_memoria()
    recibo = _submeter(
        kernel,
        PapelAutor.HUMANO,
        _no("proj", TipoNo.PROJETO),
        _no("setor", TipoNo.SETOR),
        _aresta("proj", "setor", TipoAresta.CONTEM),
        _no("sess-1", TipoNo.SESSAO),
        _aresta("setor", "sess-1", TipoAresta.CONTEM),
        _no("sess-2", TipoNo.SESSAO),
        _aresta("setor", "sess-2", TipoAresta.CONTEM),
        _no("goal", TipoNo.GOAL),
        _aresta("sess-1", "goal", TipoAresta.PRODUZ),
        _no("task", TipoNo.TASK, {"status": StatusTask.PENDENTE.value}),
        _aresta("sess-1", "task", TipoAresta.PRODUZ),
        _aresta("goal", "task", TipoAresta.DECOMPOE),
    )
    assert recibo.sucesso, recibo.mensagem
    return kernel


def _decidir_na_segunda_sessao(kernel: WriteKernel, papel: PapelAutor, destino: str = "task") -> ResultadoSubmissao:
    """Decision nova, pendurada na segunda sessão e orientando o destino."""
    return _submeter(
        kernel,
        papel,
        _no("dec", TipoNo.DECISION),
        _aresta("sess-2", "dec", TipoAresta.PRODUZ),
        _aresta("dec", destino, TipoAresta.ORIENTA),
    )


def _vista(kernel: WriteKernel, id_alvo: str, papel: PapelAutor) -> str:
    """O texto da vista do alvo pela política do papel."""
    requisicao = RequisicaoVista(id_alvo=id_alvo, papel=papel, orcamento_tokens=4000)
    return MaterializadorContexto().materializar(requisicao, kernel.obter_view()).conteudo_formatado


def test_decisao_de_outra_sessao_chega_a_vista_do_executor_nominal() -> None:
    """A decisão tomada depois, noutra sessão, aparece na vista da Task que ela orienta."""
    kernel = _montar_duas_sessoes()

    assert _decidir_na_segunda_sessao(kernel, PapelAutor.PLANEJADOR).sucesso

    vista = _vista(kernel, "task", PapelAutor.EXECUTOR)
    assert "Decisoes Que Governam Esta Tarefa" in vista
    assert "[dec]" in vista


def test_decisao_no_goal_orienta_as_tarefas_que_o_decompoem_nominal() -> None:
    """Uma Decision de arquitetura no Goal alcança cada Task da decomposição."""
    kernel = _montar_duas_sessoes()

    assert _decidir_na_segunda_sessao(kernel, PapelAutor.PLANEJADOR, destino="goal").sucesso

    assert "[dec]" in _vista(kernel, "task", PapelAutor.EXECUTOR)


def test_sem_orienta_a_decisao_de_outra_sessao_nao_chega_edge_case() -> None:
    """Caso de borda: sem a aresta, a decisão fica na sessão em que nasceu, fora da vista."""
    kernel = _montar_duas_sessoes()
    _submeter(kernel, PapelAutor.PLANEJADOR, _no("dec", TipoNo.DECISION), _aresta("sess-2", "dec", TipoAresta.PRODUZ))

    assert "[dec]" not in _vista(kernel, "task", PapelAutor.EXECUTOR)


def test_revisor_sobe_do_artefato_ate_a_decisao_que_escopa_a_tarefa_nominal() -> None:
    """Do Artifact, por deriva_de até a Task, e dali à decisão que a orienta."""
    kernel = _montar_duas_sessoes()
    assert _decidir_na_segunda_sessao(kernel, PapelAutor.PLANEJADOR).sucesso
    recibo = _submeter(
        kernel,
        PapelAutor.EXECUTOR,
        _no("art", TipoNo.ARTIFACT),
        _aresta("sess-2", "art", TipoAresta.PRODUZ),
        _aresta("art", "task", TipoAresta.DERIVA_DE),
    )
    assert recibo.sucesso, recibo.mensagem

    vista = _vista(kernel, "art", PapelAutor.REVISOR)
    assert "Decisoes Que Governam Esta Tarefa" in vista
    assert "[dec]" in vista


def test_revisor_nao_cria_orienta_edge_case() -> None:
    """Caso de borda: quem não decide não diz onde a decisão vale."""
    kernel = _montar_duas_sessoes()
    assert _decidir_na_segunda_sessao(kernel, PapelAutor.PLANEJADOR).sucesso

    recibo = _submeter(kernel, PapelAutor.REVISOR, _aresta("dec", "goal", TipoAresta.ORIENTA))

    assert recibo.sucesso is False
    assert recibo.modo_de_falha == "violacao_permissao_papel"


def test_executor_nao_mexe_nas_decisoes_que_governam_a_propria_tarefa_edge_case() -> None:
    """Caso de borda: quem executa não tira a decisão da própria tarefa nem pendura a sua no Goal."""
    kernel = _montar_duas_sessoes()
    assert _decidir_na_segunda_sessao(kernel, PapelAutor.PLANEJADOR).sucesso
    retirada = ItemPatch(op=OperacaoPatch.REMOVE, path="/arestas/orienta-dec-task")

    remocao = _submeter(kernel, PapelAutor.EXECUTOR, retirada)
    criacao = _submeter(
        kernel,
        PapelAutor.EXECUTOR,
        _no("dec-exec", TipoNo.DECISION),
        _aresta("sess-2", "dec-exec", TipoAresta.PRODUZ),
        _aresta("dec-exec", "goal", TipoAresta.ORIENTA),
    )

    assert remocao.modo_de_falha == "violacao_permissao_papel"
    assert criacao.modo_de_falha == "violacao_permissao_papel"
    assert "[dec]" in _vista(kernel, "task", PapelAutor.REVISOR)


def test_orienta_so_parte_de_decision_edge_case() -> None:
    """Caso de borda: a Task não orienta a Decision; o par invertido é recusado."""
    kernel = _montar_duas_sessoes()
    assert _decidir_na_segunda_sessao(kernel, PapelAutor.PLANEJADOR).sucesso

    recibo = _submeter(kernel, PapelAutor.HUMANO, _aresta("task", "dec", TipoAresta.ORIENTA))

    assert recibo.sucesso is False
    assert recibo.modo_de_falha == "par_de_aresta_invalido"


def test_evidencia_do_executor_aponta_o_artefato_que_avalia_nominal() -> None:
    """O teste do executor deriva do Artifact e da Task, e o revisor o encontra pelo Artifact."""
    kernel = _montar_duas_sessoes()
    recibo = _submeter(
        kernel,
        PapelAutor.EXECUTOR,
        _no("art", TipoNo.ARTIFACT),
        _aresta("sess-2", "art", TipoAresta.PRODUZ),
        _aresta("art", "task", TipoAresta.DERIVA_DE),
        _no("evi-teste", TipoNo.EVIDENCE, {"saida": "14 passed"}),
        _aresta("sess-2", "evi-teste", TipoAresta.PRODUZ),
        _aresta("evi-teste", "art", TipoAresta.DERIVA_DE),
        _aresta("evi-teste", "task", TipoAresta.DERIVA_DE),
    )

    assert recibo.sucesso, recibo.mensagem
    assert "[evi-teste]" in _vista(kernel, "art", PapelAutor.REVISOR)


def test_decisao_do_goal_desce_a_qualquer_profundidade_da_decomposicao_nominal() -> None:
    """Como as restrições, a decisão do Goal vale para a subtarefa da subtarefa e para o artefato dela."""
    kernel = _montar_duas_sessoes()
    assert _decidir_na_segunda_sessao(kernel, PapelAutor.PLANEJADOR, destino="goal").sucesso
    recibo = _submeter(
        kernel,
        PapelAutor.PLANEJADOR,
        _no("sub", TipoNo.TASK, {"status": StatusTask.PENDENTE.value}),
        _aresta("sess-2", "sub", TipoAresta.PRODUZ),
        _aresta("task", "sub", TipoAresta.DECOMPOE),
    )
    assert recibo.sucesso, recibo.mensagem
    assert _submeter(
        kernel,
        PapelAutor.EXECUTOR,
        _no("art-sub", TipoNo.ARTIFACT),
        _aresta("sess-2", "art-sub", TipoAresta.PRODUZ),
        _aresta("art-sub", "sub", TipoAresta.DERIVA_DE),
    ).sucesso

    assert "## Decisoes Que Governam Esta Tarefa\n- [dec]" in _vista(kernel, "sub", PapelAutor.EXECUTOR)
    assert "## Decisoes Que Governam Esta Tarefa\n- [dec]" in _vista(kernel, "art-sub", PapelAutor.REVISOR)


def _secao(vista: str, titulo: str) -> str:
    """O corpo de uma seção da vista, do título até a seção seguinte."""
    inicio = vista.find(f"## {titulo}")
    if inicio < 0:
        return ""
    fim = vista.find("\n## ", inicio + 1)
    return vista[inicio : fim if fim >= 0 else len(vista)]


def _tarefa_irma_com_decisao_propria(kernel: WriteKernel) -> None:
    """Uma segunda Task do mesmo Goal, com a decisão dela, as duas na mesma sessão da primeira Task."""
    recibo = _submeter(
        kernel,
        PapelAutor.PLANEJADOR,
        _no("irma", TipoNo.TASK, {"status": StatusTask.PENDENTE.value}),
        _aresta("sess-1", "irma", TipoAresta.PRODUZ),
        _aresta("goal", "irma", TipoAresta.DECOMPOE),
        _no("dec-irma", TipoNo.DECISION),
        _aresta("sess-1", "dec-irma", TipoAresta.PRODUZ),
        _aresta("dec-irma", "irma", TipoAresta.ORIENTA),
    )
    assert recibo.sucesso, recibo.mensagem


def test_decisao_da_tarefa_irma_nao_governa_esta_edge_case() -> None:
    """Caso de borda: nascer na mesma sessão não faz a decisão valer para a tarefa; ela aparece como contexto."""
    kernel = _montar_duas_sessoes()
    assert _decidir_na_segunda_sessao(kernel, PapelAutor.PLANEJADOR).sucesso
    _tarefa_irma_com_decisao_propria(kernel)

    vista = _vista(kernel, "task", PapelAutor.EXECUTOR)

    assert "[dec]" in _secao(vista, "Decisoes Que Governam Esta Tarefa")
    assert "[dec-irma]" not in _secao(vista, "Decisoes Que Governam Esta Tarefa")
    assert "[dec-irma]" in _secao(vista, "Perto Desta Tarefa, Sem Governa-la")


def test_contexto_da_sessao_cai_antes_das_decisoes_que_governam_edge_case() -> None:
    """Caso de borda: uma sessão com muitas decisões não empurra para fora a que vale para a tarefa."""
    kernel = _montar_duas_sessoes()
    assert _decidir_na_segunda_sessao(kernel, PapelAutor.PLANEJADOR).sucesso
    outras = [item for indice in range(60) for item in (
        _no(f"dec-{indice:02d}", TipoNo.DECISION), _aresta("sess-2", f"dec-{indice:02d}", TipoAresta.PRODUZ)
    )]
    assert _submeter(kernel, PapelAutor.PLANEJADOR, *outras).sucesso

    requisicao = RequisicaoVista(id_alvo="task", papel=PapelAutor.EXECUTOR, orcamento_tokens=700)
    vista = MaterializadorContexto().materializar(requisicao, kernel.obter_view()).conteudo_formatado

    assert "[dec]" in _secao(vista, "Decisoes Que Governam Esta Tarefa")
    assert "Perto Desta Tarefa, Sem Governa-la" not in vista
