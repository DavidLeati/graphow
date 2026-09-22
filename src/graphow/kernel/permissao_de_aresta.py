"""Permissão por papel na camada de arestas: quem cria e remove cada aresta, conforme o que ela liga.

A camada de arestas retornava sucesso para qualquer papel e deixava um
executor reescopar a própria tarefa. Aqui o RoleGate consulta a matriz de
donos (kernel/matriz_papeis.py) para a operação e o papel correntes, amplia os
donos sob autonomia ilimitada e, quando o par de tipos das pontas tem entrada
própria, deixa o par prevalecer: `substitui` entre Aprendizados é consolidação
de memória, e a escreve quem registra Aprendizado.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado
from graphow.core.types import NivelAutonomiaProjeto, PapelAutor, TipoAresta, TipoNo
from graphow.kernel.matriz_papeis import (
    DonosDeAresta,
    obter_donos_de_aresta,
    obter_donos_sob_autonomia_ilimitada,
)
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch, PropostaPatch, ResultadoValidacao
from graphow.kernel.rastreio_projeto import RastreadorProjetoAncestral

SEGMENTOS_DE_ELEMENTO_INTEIRO: int = 2


@dataclass(frozen=True)
class ContextoPapel:
    """Estado compartilhado por todas as verificações de uma mesma proposta.

    `estado_com_lote` inclui os nós e arestas que o próprio lote cria: é o que
    permite resolver o projeto ancestral de uma Sessao recém-criada pela aresta
    `contem` que veio junto, em vez de por chaves dentro do valor do nó.
    """

    proposta: PropostaPatch
    estado: GrafoEstado
    estado_com_lote: GrafoEstado


def projeto_eh_ilimitado(projeto_id: str, estado: GrafoEstado) -> bool:
    """Checa se o nó de projeto possui configuração de autonomia ilimitada."""
    projeto = estado.nos.get(projeto_id)
    if projeto is None or projeto.tipo != TipoNo.PROJETO:
        return False
    nivel = str(projeto.propriedades.get("nivel_autonomia", "")).lower()
    return nivel == NivelAutonomiaProjeto.ILIMITADO.value


class PermissaoDeAresta:
    """Aplica a matriz de donos de aresta à operação de um lote, sob o papel do autor."""

    def __init__(self, rastreador: RastreadorProjetoAncestral) -> None:
        self._rastreador: RastreadorProjetoAncestral = rastreador

    def validar(self, segmentos: Sequence[str], item: ItemPatch, contexto: ContextoPapel) -> ResultadoValidacao:
        """Consulta a matriz de donos de aresta para a operação e o papel correntes."""
        tipo = self._identificar_tipo(segmentos, item, contexto.estado)
        if tipo is None:
            return ResultadoValidacao.sucesso()
        eh_remocao = item.op == OperacaoPatch.REMOVE
        par = self._par_de_tipos(segmentos, item, contexto)
        donos = self._donos_aplicaveis(tipo, item, contexto, par=par)
        if donos.autoriza(contexto.proposta.papel, eh_remocao):
            return ResultadoValidacao.sucesso()
        return self._recusar(tipo, contexto.proposta.papel, eh_remocao, par=par)

    def _donos_aplicaveis(
        self,
        tipo: TipoAresta,
        item: ItemPatch,
        contexto: ContextoPapel,
        *,
        par: tuple[TipoNo, TipoNo] | None = None,
    ) -> DonosDeAresta:
        """Amplia os donos quando a aresta pertence a um projeto autônomo.

        Sem isto a autonomia ilimitada voltaria a ser inerte por outro
        caminho: o agente criaria o nó Setor e seria barrado na aresta
        `contem` que o prende ao Projeto.
        """
        if not self._sob_autonomia_ilimitada(item, contexto):
            return obter_donos_de_aresta(tipo, par)
        return obter_donos_sob_autonomia_ilimitada(tipo, par)

    def _sob_autonomia_ilimitada(self, item: ItemPatch, contexto: ContextoPapel) -> bool:
        """Rastreia o projeto a partir das duas pontas declaradas da aresta."""
        for id_ponta in self._pontas_declaradas(item):
            projeto = self._rastreador.rastrear(id_ponta, contexto.estado_com_lote)
            if projeto is not None and projeto_eh_ilimitado(projeto, contexto.estado_com_lote):
                return True
        return False

    def _pontas_declaradas(self, item: ItemPatch) -> tuple[str, ...]:
        """Identificadores de origem e destino declarados no valor da aresta."""
        if not isinstance(item.value, dict):
            return ()
        pontas = (item.value.get("origem_id"), item.value.get("destino_id"))
        return tuple(str(ponta) for ponta in pontas if ponta)

    def _pontas_existentes(self, segmentos: Sequence[str], estado: GrafoEstado) -> tuple[str, ...]:
        """Na remoção, as pontas vêm da aresta já projetada."""
        if len(segmentos) < SEGMENTOS_DE_ELEMENTO_INTEIRO:
            return ()
        aresta = estado.arestas.get(segmentos[1])
        return (aresta.origem_id, aresta.destino_id) if aresta is not None else ()

    def _par_de_tipos(
        self,
        segmentos: Sequence[str],
        item: ItemPatch,
        contexto: ContextoPapel,
    ) -> tuple[TipoNo, TipoNo] | None:
        """Os tipos das duas pontas, lidos do lote projetado; None quando alguma não existe.

        Uma aresta pode ter dono diferente conforme o que liga: `substitui`
        entre Aprendizados é consolidação de memória, e a escreve quem
        registra Aprendizado (kernel/matriz_papeis.py).
        """
        pontas = self._pontas_declaradas(item) or self._pontas_existentes(segmentos, contexto.estado)
        if len(pontas) != 2:
            return None
        origem = contexto.estado_com_lote.nos.get(pontas[0])
        destino = contexto.estado_com_lote.nos.get(pontas[1])
        if origem is None or destino is None:
            return None
        return (origem.tipo, destino.tipo)

    def _recusar(
        self,
        tipo: TipoAresta,
        papel: PapelAutor,
        eh_remocao: bool,
        *,
        par: tuple[TipoNo, TipoNo] | None = None,
    ) -> ResultadoValidacao:
        """Explica ao agente quem detém a aresta que ele tentou mexer."""
        verbo = "remover" if eh_remocao else "criar"
        donos = obter_donos_de_aresta(tipo, par)
        autorizados = sorted(p.value for p in (donos.remocao if eh_remocao else donos.adicao))
        return ResultadoValidacao.falha(
            f"Papel '{papel.value}' não pode {verbo} aresta '{tipo.value}'",
            "RoleGate",
            {"tipo_aresta": tipo.value, "papeis_autorizados": ", ".join(autorizados)},
            modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
        )

    def _identificar_tipo(
        self,
        segmentos: Sequence[str],
        item: ItemPatch,
        estado: GrafoEstado,
    ) -> TipoAresta | None:
        """Lê o tipo do valor proposto ou, na remoção, da aresta já projetada."""
        declarado = item.value.get("tipo") if isinstance(item.value, dict) else None
        if declarado is not None:
            return self._converter_tipo(declarado)
        if len(segmentos) < SEGMENTOS_DE_ELEMENTO_INTEIRO:
            return None
        aresta = estado.arestas.get(segmentos[1])
        return aresta.tipo if aresta is not None else None

    def _converter_tipo(self, declarado: Any) -> TipoAresta | None:
        """Converte o tipo textual, deixando a forma inválida para o SchemaGate."""
        try:
            return TipoAresta(declarado)
        except ValueError:
            return None
