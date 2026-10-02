"""O árbitro não promove o Aprendizado que ele mesmo registrou: a autoria vem da proveniência do nó."""

from dataclasses import replace

from graphow.core.models import GrafoEstado, ProvenienciaNo
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch
from tests.kernel.cenario_governanca import (
    PRESET_ARBITRAGEM,
    criar_aresta,
    criar_no,
    montar_estado,
    validar,
)


def _estado_com_autor_do_aprendizado(autor: str) -> GrafoEstado:
    """Arbitragem máxima, com o Aprendizado `a2` registrado pelo autor dado."""
    estado = montar_estado(global_=PRESET_ARBITRAGEM)
    registrado = replace(estado.nos["a2"], proveniencia=ProvenienciaNo(autor=autor, papel="executor"))
    return GrafoEstado(nos={**estado.nos, "a2": registrado}, arestas=estado.arestas)


def _promover(destino: str = "setor") -> ItemPatch:
    """Criação do vale_para de `a2` ao destino."""
    return criar_aresta(f"vale-a2-{destino}", "a2", destino, TipoAresta.VALE_PARA)


def test_arbitro_promove_aprendizado_de_outro_autor_nominal() -> None:
    """Aprendizado registrado por um executor é promovido ao Setor e ao Projeto pelo árbitro."""
    estado = _estado_com_autor_do_aprendizado("executor-1#aaaa")

    assert validar(PapelAutor.ARBITRO, estado, _promover("setor"), autor="arbitro-1#bbbb").aprovado
    assert validar(PapelAutor.ARBITRO, estado, _promover("proj"), autor="arbitro-1#bbbb").aprovado


def test_arbitro_nao_promove_o_aprendizado_que_registrou_edge_case() -> None:
    """Caso de borda: o sufixo de conexão muda a cada conexão, e a comparação o ignora."""
    estado = _estado_com_autor_do_aprendizado("arbitro-1#aaaa")

    for destino in ("setor", "proj"):
        resultado = validar(PapelAutor.ARBITRO, estado, _promover(destino), autor="arbitro-1#bbbb")
        assert not resultado.aprovado
        assert "causa propria" in str(resultado.mensagem_erro)
        assert "a2" in str(resultado.mensagem_erro)


def test_autor_com_nome_parecido_nao_e_autoria_propria_edge_case() -> None:
    """Caso de borda: 'arbitro-10' não é 'arbitro-1'."""
    estado = _estado_com_autor_do_aprendizado("arbitro-10#aaaa")

    assert validar(PapelAutor.ARBITRO, estado, _promover(), autor="arbitro-1#bbbb").aprovado


def test_humano_promove_o_proprio_aprendizado_edge_case() -> None:
    """Caso de borda: a barreira é do árbitro; o humano que registrou pode promover."""
    estado = _estado_com_autor_do_aprendizado("david")

    assert validar(PapelAutor.HUMANO, estado, _promover(), autor="david").aprovado


def test_aprendizado_criado_e_promovido_no_mesmo_lote_e_recusado_edge_case() -> None:
    """Caso de borda: criar e promover no mesmo lote é promover o próprio; o nó ainda não tem proveniência."""
    estado = montar_estado(global_=PRESET_ARBITRAGEM)
    operacoes = (
        criar_no("a3", TipoNo.APRENDIZADO),
        criar_aresta("prod-a3", "sess", "a3", TipoAresta.PRODUZ),
        criar_aresta("vale-a3-setor", "a3", "setor", TipoAresta.VALE_PARA),
    )

    resultado = validar(PapelAutor.ARBITRO, estado, *operacoes, autor="arbitro-1#bbbb")

    assert not resultado.aprovado
    assert "causa propria" in str(resultado.mensagem_erro)


def test_aprendizado_sem_proveniencia_nao_e_autoria_propria_edge_case() -> None:
    """Caso de borda: nó antigo sem autor gravado não trava o árbitro."""
    estado = _estado_com_autor_do_aprendizado("")

    assert validar(PapelAutor.ARBITRO, estado, _promover(), autor="arbitro-1#bbbb").aprovado
