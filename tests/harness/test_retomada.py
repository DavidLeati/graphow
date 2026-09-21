"""Testes da vista de retomada: o que o hook de início imprime para o agente ler antes de trabalhar."""

from graphow.context.fechamento import ACAO_DE_CONDENSACAO
from graphow.context.protocolo import TITULO_DO_PROTOCOLO
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.harness.retomada import (
    LIMITE_DE_APRENDIZADOS,
    SEM_APRENDIZADOS,
    SEM_REGISTROS,
    SEM_SESSAO_ANTERIOR,
    TITULO_DA_SESSAO_RETOMADA,
    TITULO_DA_VISTA,
    PedidoDeRetomada,
    montar_vista_de_retomada,
)
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.reactive.condensacao import montar_proposta_de_condensacao


def _no(id_no: str, tipo: TipoNo, rotulo: str, **propriedades: str) -> ItemPatch:
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


def _submeter(kernel: WriteKernel, operacoes: list[ItemPatch]) -> None:
    """Submete o lote como humano, exigindo aceitação."""
    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="cenario")
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))
    assert recibo.sucesso, recibo.mensagem


def _aprendizado(id_no: str, sessao: str, origem: str, *, alcance: str = "") -> list[ItemPatch]:
    """Um Aprendizado produzido pela sessão, com origem e, se pedido, promovido a um alvo."""
    operacoes = [
        _no(id_no, TipoNo.APRENDIZADO, f"Licao {id_no}", como_aplicar=f"Aplique {id_no}"),
        _aresta(sessao, id_no, TipoAresta.PRODUZ),
        _aresta(id_no, origem, TipoAresta.DERIVA_DE),
    ]
    if alcance:
        operacoes.append(_aresta(id_no, alcance, TipoAresta.VALE_PARA))
    return operacoes


def _ambiente() -> WriteKernel:
    """Projeto, Setor Memoria, a sessão anterior encerrada com trabalho, e a sessão que abre."""
    kernel = montar_kernel_em_memoria()
    _submeter(
        kernel,
        [
            _no("proj-1", TipoNo.PROJETO, "meu-repo"),
            _no("setor-1", TipoNo.SETOR, "Memoria"),
            _aresta("proj-1", "setor-1", TipoAresta.CONTEM),
            _no("sess-antes", TipoNo.SESSAO, "Sessao anterior", status="concluida"),
            _aresta("setor-1", "sess-antes", TipoAresta.CONTEM),
            _no("dec-1", TipoNo.DECISION, "Usar SQLite"),
            _aresta("sess-antes", "dec-1", TipoAresta.PRODUZ),
            _no("evi-1", TipoNo.EVIDENCE, "Teste passou"),
            _aresta("sess-antes", "evi-1", TipoAresta.PRODUZ),
            _no("sess-nova", TipoNo.SESSAO, "Sessao nova", status="ativa"),
            _aresta("setor-1", "sess-nova", TipoAresta.CONTEM),
        ],
    )
    return kernel


def _vista(kernel: WriteKernel, id_sessao: str = "sess-nova", id_setor: str = "setor-1") -> tuple[str, ...]:
    """A vista montada sobre a projeção atual do kernel."""
    return montar_vista_de_retomada(PedidoDeRetomada(view=kernel.obter_view(), id_sessao=id_sessao, id_setor=id_setor))


def test_vista_traz_onde_aprendizados_sessao_anterior_e_protocolo_nominal() -> None:
    """Numa saída só: onde a sessão mora, o que vale aqui, o que a anterior deixou e o que fazer."""
    kernel = _ambiente()
    _submeter(kernel, _aprendizado("apr-prom", "sess-antes", "dec-1", alcance="proj-1"))
    _submeter(kernel, _aprendizado("apr-local", "sess-antes", "evi-1"))

    vista = _vista(kernel)
    texto = "\n".join(vista)

    assert vista[0] == f"## {TITULO_DA_VISTA}"
    assert vista[1] == "Projeto meu-repo (proj-1) | Setor Memoria (setor-1) | Sessao sess-nova"
    assert texto.index("[apr-prom]") < texto.index("[apr-local]")
    assert "- [sess-antes] Sessao anterior" in texto
    assert "status concluida | 2 Aprendizado, 1 Decision, 1 Evidence" in texto
    assert "vigora: dec-1" in texto
    assert TITULO_DO_PROTOCOLO in texto
    assert "`ler_vista` na sessao sess-nova" in texto
    assert TITULO_DA_SESSAO_RETOMADA not in texto


def test_primeira_sessao_sem_aprendizados_diz_isso_edge_case() -> None:
    """Caso de borda: sem memória ainda, a vista diz por onde ela começa em vez de calar."""
    kernel = montar_kernel_em_memoria()
    _submeter(
        kernel,
        [
            _no("proj-1", TipoNo.PROJETO, "meu-repo"),
            _no("setor-1", TipoNo.SETOR, "Memoria"),
            _aresta("proj-1", "setor-1", TipoAresta.CONTEM),
            _no("sess-nova", TipoNo.SESSAO, "Sessao nova"),
            _aresta("setor-1", "sess-nova", TipoAresta.CONTEM),
        ],
    )

    vista = _vista(kernel)

    assert SEM_APRENDIZADOS in vista
    assert SEM_SESSAO_ANTERIOR in vista


def test_sessao_anterior_so_com_telemetria_e_dita_sem_registros_edge_case() -> None:
    """Caso de borda: dezessete sessões só tinham o Run; a vista nomeia essa ausência."""
    kernel = montar_kernel_em_memoria()
    _submeter(
        kernel,
        [
            _no("proj-1", TipoNo.PROJETO, "meu-repo"),
            _no("setor-1", TipoNo.SETOR, "Memoria"),
            _aresta("proj-1", "setor-1", TipoAresta.CONTEM),
            _no("sess-vazia", TipoNo.SESSAO, "Sessao vazia", status="concluida"),
            _aresta("setor-1", "sess-vazia", TipoAresta.CONTEM),
            _no("sess-nova", TipoNo.SESSAO, "Sessao nova"),
            _aresta("setor-1", "sess-nova", TipoAresta.CONTEM),
        ],
    )

    vista = _vista(kernel)

    assert "- [sess-vazia] Sessao vazia" in vista
    assert SEM_REGISTROS in vista


def test_condensacao_pendente_da_sessao_anterior_e_apontada_pela_task_nominal() -> None:
    """A Task que o motor abriu e ninguém pegou chega ao agente seguinte com o id para assumir."""
    kernel = _ambiente()
    sessao = kernel.obter_view().obter_no("sess-antes")
    assert sessao is not None
    assert kernel.submeter_patch(montar_proposta_de_condensacao(sessao)).sucesso

    texto = "\n".join(_vista(kernel))

    assert "condensacao pendente: Task task-condensar-" in texto


def test_condensacao_escrita_aparece_no_lugar_do_pedido_nominal() -> None:
    """Escrita a Note de condensação, a vista abre por ela e não pede outra."""
    kernel = _ambiente()
    _submeter(
        kernel,
        [
            _no(
                "note-cond",
                TipoNo.NOTE,
                "Condensacao",
                acao=ACAO_DE_CONDENSACAO,
                id_alvo="sess-antes",
                corpo="Decidimos SQLite\n  porque o log e append-only.",
            ),
            _aresta("sess-antes", "note-cond", TipoAresta.PRODUZ),
        ],
    )

    texto = "\n".join(_vista(kernel))

    assert "condensacao [note-cond]: Decidimos SQLite porque o log e append-only." in texto
    assert "condensacao pendente" not in texto


def test_sessao_retomada_mostra_o_proprio_trabalho_edge_case() -> None:
    """Caso de borda: o ambiente retoma uma sessão que já registrou; ela se apresenta a si mesma."""
    kernel = _ambiente()
    _submeter(kernel, [_no("evi-nova", TipoNo.EVIDENCE, "Achado desta sessao"), _aresta("sess-nova", "evi-nova", TipoAresta.PRODUZ)])

    vista = _vista(kernel)

    assert TITULO_DA_SESSAO_RETOMADA in vista
    assert "  status ativa | 1 Evidence" in vista


def test_excedente_de_aprendizados_e_anunciado_edge_case() -> None:
    """Caso de borda: a vista tem teto; o que não coube é contado, não escondido."""
    kernel = _ambiente()
    for numero in range(LIMITE_DE_APRENDIZADOS + 2):
        _submeter(kernel, _aprendizado(f"apr-{numero:02d}", "sess-antes", "evi-1"))

    vista = _vista(kernel)

    assert sum(1 for linha in vista if linha.startswith("- [apr-")) == LIMITE_DE_APRENDIZADOS
    assert any("e mais 2" in linha for linha in vista)


def test_setor_inexistente_devolve_vista_vazia_edge_case() -> None:
    """Caso de borda: sem Setor não há onde a memória morar, e o hook não imprime lixo."""
    kernel = _ambiente()

    assert montar_vista_de_retomada(PedidoDeRetomada(view=kernel.obter_view(), id_sessao="s", id_setor="setor-fantasma")) == ()
