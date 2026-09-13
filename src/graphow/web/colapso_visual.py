"""Recorte do canvas no servidor: colapso em super-nós, escopo ativo e gargalos.

O canvas devolvia o grafo inteiro em toda requisição — 215 KB e 191 cartões para
um projeto de porte médio — e o único nível de detalhe existente era uma classe
CSS que encolhia o cartão no zoom. Encolher o cartão não reduz dado nenhum: os
215 KB continuavam atravessando a rede e o navegador continuava montando 191
elementos. Por isso o recorte mora aqui, e não no cliente.

São três recortes independentes e combináveis. O colapso mostra só a camada de
navegação até o nível pedido, cada contêiner carregando o agregado da própria
subárvore. O escopo ativo mantém o que está perto de trabalho não concluído. O
caminho crítico mantém quem participa de alguma dependência. O que sobra é
sempre anunciado em `recorte`, para a interface poder dizer o que escondeu em vez
de simplesmente mostrar menos.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from graphow.core.types import TipoNo
from graphow.projection.graph_view import GrafoView
from graphow.projection.working_set import RAIO_PADRAO

# Colapsar "em setor" mostra o Projeto e os Setores, e esconde o que pende deles.
CAMADAS_POR_NIVEL: Mapping[str, tuple[TipoNo, ...]] = {
    "projeto": (TipoNo.PROJETO,),
    "setor": (TipoNo.PROJETO, TipoNo.SETOR),
    "sessao": (TipoNo.PROJETO, TipoNo.SETOR, TipoNo.SESSAO),
}

NIVEIS_ACEITOS: tuple[str, ...] = tuple(CAMADAS_POR_NIVEL)


@dataclass(frozen=True)
class OpcoesDeRecorteVisual:
    """Os três recortes que a tela pode pedir, combináveis entre si."""

    colapsar_em: str = ""
    escopo_ativo: bool = False
    raio: int = RAIO_PADRAO
    caminho_critico: bool = False

    @property
    def nivel_de_colapso(self) -> str:
        """Nível saneado, ou vazio quando o pedido não nomeia um nível conhecido."""
        nivel = self.colapsar_em.strip().lower()
        return nivel if nivel in CAMADAS_POR_NIVEL else ""

    @property
    def pede_algum_recorte(self) -> bool:
        """Indica se há qualquer filtro a aplicar sobre o grafo completo."""
        return bool(self.nivel_de_colapso) or self.escopo_ativo or self.caminho_critico


@dataclass(frozen=True)
class SelecaoVisual:
    """Quais nós a tela deve receber, e a explicação do que ficou de fora."""

    ids: frozenset[str] = field(default_factory=frozenset)
    total_no_grafo: int = 0
    filtros_aplicados: tuple[str, ...] = field(default_factory=tuple)
    nos_orfaos: tuple[str, ...] = field(default_factory=tuple)
    detalhes: Mapping[str, Any] = field(default_factory=dict)

    @property
    def total_oculto(self) -> int:
        """Quantos nós do grafo não vão para a tela neste recorte."""
        return max(0, self.total_no_grafo - len(self.ids))

    def em_dicionario(self) -> dict[str, Any]:
        """Bloco `recorte` da resposta, para a interface explicar o que escondeu."""
        return {
            "filtros": list(self.filtros_aplicados),
            "total_no_grafo": self.total_no_grafo,
            "total_exibido": len(self.ids),
            "total_oculto": self.total_oculto,
            "nos_orfaos": list(self.nos_orfaos),
            **dict(self.detalhes),
        }


class RecortadorVisual:
    """Aplica os recortes pedidos e devolve os identificadores que sobrevivem."""

    def __init__(self, view: GrafoView) -> None:
        self._view: GrafoView = view

    def selecionar(self, opcoes: OpcoesDeRecorteVisual) -> SelecaoVisual:
        """Interseca os recortes pedidos sobre o conjunto de nós do grafo."""
        todos = frozenset(no.id for no in self._view.listar_todos_os_nos())
        base = SelecaoVisual(
            ids=todos,
            total_no_grafo=len(todos),
            nos_orfaos=self._view.indice_de_rollup.nos_orfaos,
        )
        if not opcoes.pede_algum_recorte:
            return base
        return self._aplicar(base, opcoes)

    def _aplicar(self, base: SelecaoVisual, opcoes: OpcoesDeRecorteVisual) -> SelecaoVisual:
        """Encadeia os filtros, acumulando o nome de cada um e seus detalhes."""
        ids = set(base.ids)
        filtros: list[str] = []
        detalhes: dict[str, Any] = {}
        ids &= self._ids_do_colapso(opcoes, filtros, detalhes)
        ids &= self._ids_do_escopo(opcoes, filtros, detalhes)
        ids &= self._ids_do_caminho(opcoes, filtros, detalhes)
        return SelecaoVisual(
            ids=frozenset(ids),
            total_no_grafo=base.total_no_grafo,
            filtros_aplicados=tuple(filtros),
            nos_orfaos=base.nos_orfaos,
            detalhes=detalhes,
        )

    def _ids_do_colapso(
        self,
        opcoes: OpcoesDeRecorteVisual,
        filtros: list[str],
        detalhes: dict[str, Any],
    ) -> set[str]:
        """Mantém apenas a camada de navegação até o nível pedido."""
        nivel = opcoes.nivel_de_colapso
        if not nivel:
            return {no.id for no in self._view.listar_todos_os_nos()}
        camadas = frozenset(CAMADAS_POR_NIVEL[nivel])
        filtros.append(f"colapsado_em:{nivel}")
        detalhes["colapsado_em"] = nivel
        return {no.id for no in self._view.listar_todos_os_nos() if no.tipo in camadas}

    def _ids_do_escopo(
        self,
        opcoes: OpcoesDeRecorteVisual,
        filtros: list[str],
        detalhes: dict[str, Any],
    ) -> set[str]:
        """Mantém o que está a até `raio` saltos do trabalho não concluído."""
        if not opcoes.escopo_ativo:
            return {no.id for no in self._view.listar_todos_os_nos()}
        escopo = self._view.calcular_escopo_ativo(opcoes.raio)
        filtros.append(f"escopo_ativo:raio_{escopo.raio}")
        detalhes["escopo_ativo"] = escopo.em_dicionario()
        if escopo.esta_vazio:
            return {no.id for no in self._view.listar_todos_os_nos()}
        return set(escopo.ids)

    def _ids_do_caminho(
        self,
        opcoes: OpcoesDeRecorteVisual,
        filtros: list[str],
        detalhes: dict[str, Any],
    ) -> set[str]:
        """Mantém quem participa de alguma dependência, mais as tarefas abertas."""
        if not opcoes.caminho_critico:
            return {no.id for no in self._view.listar_todos_os_nos()}
        caminho = self._view.calcular_caminho_critico()
        filtros.append("caminho_critico")
        detalhes["caminho_critico"] = caminho.em_dicionario()
        if caminho.esta_vazio:
            return {no.id for no in self._view.listar_todos_os_nos()}
        return set(caminho.ids)
