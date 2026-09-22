"""Testes do ambiente padrão: Projeto do repositório e Setor `Memoria`, criados uma vez e reaproveitados."""

from pathlib import Path

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.harness.ambiente_padrao import (
    ROTULO_DO_SETOR_DE_MEMORIA,
    AmbientePadrao,
    GarantidorDeAmbientePadrao,
    gerar_slug,
)
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel


def _no(id_no: str, tipo: TipoNo, rotulo: str) -> ItemPatch:
    """Operação de criação de nó."""
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value={"id": id_no, "tipo": tipo.value, "rotulo": rotulo})


def _contem(origem: str, destino: str) -> ItemPatch:
    """Operação de criação da aresta de contenção."""
    id_aresta = f"contem-{origem}-{destino}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": TipoAresta.CONTEM.value},
    )


def _submeter_como_humano(kernel: WriteKernel, operacoes: list[ItemPatch]) -> None:
    """O que o humano já estruturou antes de o harness rodar."""
    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="humano")
    assert kernel.submeter_patch(PropostaPatch.criar(dados)).sucesso


def _submeter_como_harness(kernel: WriteKernel, operacoes: list[ItemPatch]) -> None:
    """O que o hook já criou numa sessão anterior."""
    dados = DadosPropostaPatch(autor="harness", papel=PapelAutor.SISTEMA, operacoes=operacoes, justificativa="hook")
    assert kernel.submeter_patch(PropostaPatch.criar(dados)).sucesso


def test_slug_tira_acentos_espacos_e_maiusculas_nominal() -> None:
    """O nome da pasta vira identificador estável."""
    assert gerar_slug("Memória em Camadas 2") == "memoria-em-camadas-2"
    assert gerar_slug("graphow") == "graphow"


def test_slug_vazio_cai_na_reserva_edge_case() -> None:
    """Caso de borda: um nome só de símbolos não pode virar id vazio."""
    assert gerar_slug("!!!") == "projeto"


def test_ambiente_deriva_ids_e_rotulos_do_nome_do_repositorio_nominal(tmp_path: Path) -> None:
    """Projeto com o nome da pasta, Setor `Memoria` com id derivado."""
    (tmp_path / "meu-repo" / ".git").mkdir(parents=True)

    ambiente = AmbientePadrao.do_diretorio(str(tmp_path / "meu-repo" / "src"))

    assert ambiente.nome_do_projeto == "meu-repo"
    assert ambiente.id_projeto == "proj-meu-repo"
    assert ambiente.id_setor == "setor-meu-repo-memoria"
    assert ambiente.rotulo_do_projeto == "meu-repo"
    assert ambiente.rotulo_do_setor == ROTULO_DO_SETOR_DE_MEMORIA


def test_garantir_cria_projeto_e_setor_como_sistema_uma_vez_nominal() -> None:
    """A primeira sessão cria o ambiente; a segunda o reaproveita sem duplicar."""
    kernel = montar_kernel_em_memoria()
    ambiente = AmbientePadrao(nome_do_projeto="graphow")
    garantidor = GarantidorDeAmbientePadrao(kernel)

    primeiro = garantidor.garantir(ambiente)
    segundo = garantidor.garantir(ambiente)

    assert primeiro == segundo == "setor-graphow-memoria"
    view = kernel.obter_view()
    projeto = view.obter_no("proj-graphow")
    setor = view.obter_no("setor-graphow-memoria")
    assert projeto is not None and projeto.rotulo == "graphow"
    assert setor is not None and setor.rotulo == "Memoria"
    assert setor.proveniencia.papel == PapelAutor.SISTEMA.value
    assert [no.id for no in view.obter_filhos_por_contencao("proj-graphow")] == ["setor-graphow-memoria"]
    assert len(view.listar_nos_por_tipo(TipoNo.PROJETO)) == 1


def test_projeto_de_trabalho_com_o_nome_do_repositorio_nao_recebe_as_sessoes_do_hook_nominal() -> None:
    """Um Projeto `Graphow` criado à mão é trabalho: o hook abre o próprio ambiente ao lado dele."""
    kernel = montar_kernel_em_memoria()
    _submeter_como_humano(kernel, [_no("projeto-do-david", TipoNo.PROJETO, "Graphow")])

    id_setor = GarantidorDeAmbientePadrao(kernel).garantir(AmbientePadrao(nome_do_projeto="graphow"))

    view = kernel.obter_view()
    assert id_setor == "setor-graphow-memoria"
    assert view.obter_filhos_por_contencao("projeto-do-david") == []
    assert [no.id for no in view.obter_filhos_por_contencao("proj-graphow")] == [id_setor]
    assert view.obter_no("proj-graphow").proveniencia.papel == PapelAutor.SISTEMA.value


def test_id_derivado_ocupado_por_projeto_de_trabalho_ganha_sufixo_edge_case() -> None:
    """Caso de borda: o humano criou `proj-graphow` à mão; o ambiente nasce em `proj-graphow-2` e é achado de novo."""
    kernel = montar_kernel_em_memoria()
    _submeter_como_humano(kernel, [_no("proj-graphow", TipoNo.PROJETO, "graphow")])
    garantidor = GarantidorDeAmbientePadrao(kernel)

    primeiro = garantidor.garantir(AmbientePadrao(nome_do_projeto="graphow"))
    segundo = garantidor.garantir(AmbientePadrao(nome_do_projeto="graphow"))

    view = kernel.obter_view()
    assert primeiro == segundo == "setor-graphow-memoria"
    assert view.obter_filhos_por_contencao("proj-graphow") == []
    assert [no.id for no in view.obter_filhos_por_contencao("proj-graphow-2")] == [primeiro]
    assert len(view.listar_nos_por_tipo(TipoNo.PROJETO)) == 2


def test_setor_memoria_antigo_dentro_de_projeto_de_trabalho_fica_onde_esta_edge_case() -> None:
    """Caso de borda: o hook de antes pendurou `setor-graphow-memoria` num Projeto do humano.

    O ambiente novo não pode tentar criar o mesmo id, ou o lote falharia e as
    sessões nasceriam sem Setor: ele ganha `setor-graphow-memoria-2`.
    """
    kernel = montar_kernel_em_memoria()
    _submeter_como_humano(kernel, [_no("projeto-do-david", TipoNo.PROJETO, "graphow")])
    _submeter_como_harness(
        kernel,
        [_no("setor-graphow-memoria", TipoNo.SETOR, "Memoria"), _contem("projeto-do-david", "setor-graphow-memoria")],
    )

    id_setor = GarantidorDeAmbientePadrao(kernel).garantir(AmbientePadrao(nome_do_projeto="graphow"))

    view = kernel.obter_view()
    assert id_setor == "setor-graphow-memoria-2"
    assert [no.id for no in view.obter_filhos_por_contencao("proj-graphow")] == [id_setor]
    assert [no.id for no in view.obter_filhos_por_contencao("projeto-do-david")] == ["setor-graphow-memoria"]


def test_setor_memoria_que_ja_existe_no_ambiente_e_reaproveitado_pelo_rotulo_nominal() -> None:
    """Um Setor chamado `Memoria` dentro do ambiente do hook é o Setor dele, seja qual for o id."""
    kernel = montar_kernel_em_memoria()
    _submeter_como_harness(kernel, [_no("proj-graphow", TipoNo.PROJETO, "graphow")])
    _submeter_como_humano(kernel, [_no("setor-x", TipoNo.SETOR, "memoria"), _contem("proj-graphow", "setor-x")])

    id_setor = GarantidorDeAmbientePadrao(kernel).garantir(AmbientePadrao(nome_do_projeto="graphow"))

    assert id_setor == "setor-x"
    assert len(kernel.obter_view().listar_nos_por_tipo(TipoNo.SETOR)) == 1


def test_outros_setores_do_ambiente_nao_sao_confundidos_com_a_memoria_edge_case() -> None:
    """Caso de borda: um Setor `Engenharia` no ambiente do hook não é o Setor de memória."""
    kernel = montar_kernel_em_memoria()
    _submeter_como_harness(kernel, [_no("proj-graphow", TipoNo.PROJETO, "graphow")])
    _submeter_como_humano(kernel, [_no("setor-eng", TipoNo.SETOR, "Engenharia"), _contem("proj-graphow", "setor-eng")])

    id_setor = GarantidorDeAmbientePadrao(kernel).garantir(AmbientePadrao(nome_do_projeto="graphow"))

    assert id_setor == "setor-graphow-memoria"
    assert {no.id for no in kernel.obter_view().obter_filhos_por_contencao("proj-graphow")} == {"setor-eng", id_setor}
