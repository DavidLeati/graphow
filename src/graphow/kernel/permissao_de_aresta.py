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
from graphow.core.models import ArestaGrafo, GrafoEstado
from graphow.core.ontologia import ARESTAS_DE_CONTENCAO
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
        if item.op == OperacaoPatch.REMOVE:
            aresta = contexto.estado_com_lote.arestas.get(segmentos[1]) if len(segmentos) >= SEGMENTOS_DE_ELEMENTO_INTEIRO else None
            return self.validar_remocao(aresta, contexto) if aresta is not None else ResultadoValidacao.sucesso()
        tipo = self._identificar_tipo(item)
        if tipo is None:
            return ResultadoValidacao.sucesso()
        par = self._par_de_tipos(self._pontas_declaradas(item), contexto)
        donos = self._donos_aplicaveis(tipo, item, contexto, par=par)
        if donos.autoriza(contexto.proposta.papel, False):
            return ResultadoValidacao.sucesso()
        return self._recusar(tipo, contexto.proposta.papel, False, par=par)

    def validar_remocao(self, aresta: ArestaGrafo, contexto: ContextoPapel) -> ResultadoValidacao:
        """Julga a remoção pela aresta como ela está no grafo, nunca pelo valor enviado.

        O tipo e as pontas vinham do `value` da operação quando ele trazia
        algum: um executor removia a `bloqueia` que o travava declarando
        `"tipo": "justifica"`, e concluía a Task no lote seguinte. A aresta
        criada antes, no mesmo lote, conta como existente: a antevisão do lote
        a inclui. Remover não é ampliado pela autonomia do projeto.
        """
        par = self._par_de_tipos((aresta.origem_id, aresta.destino_id), contexto)
        if obter_donos_de_aresta(aresta.tipo, par).autoriza(contexto.proposta.papel, True):
            return ResultadoValidacao.sucesso()
        return self._recusar(aresta.tipo, contexto.proposta.papel, True, par=par)

    def validar_remocao_em_cascata(self, id_no: str, contexto: ContextoPapel) -> ResultadoValidacao:
        """Remover um nó leva junto as arestas dele, e cada uma exige o poder de removê-la.

        A projeção apaga toda aresta que toca o nó removido. Um executor
        removia a Sessão e deixava a Question e a Constraint dela fora da
        hierarquia; um planejador removia a Task e levava a `bloqueia` que só o
        humano retira. A aresta de contenção que pendura o próprio nó sai com
        ele sem deixar ninguém solto, e fica de fora.
        """
        for aresta in contexto.estado_com_lote.arestas.values():
            if not self._sai_na_cascata(aresta, id_no):
                continue
            resultado = self.validar_remocao(aresta, contexto)
            if not resultado.aprovado:
                return self._recusar_cascata(id_no, aresta, contexto.proposta.papel)
        return ResultadoValidacao.sucesso()

    def _sai_na_cascata(self, aresta: ArestaGrafo, id_no: str) -> bool:
        """A aresta toca o nó e não é a contenção que o pendura."""
        if aresta.destino_id == id_no:
            return aresta.tipo not in ARESTAS_DE_CONTENCAO
        return aresta.origem_id == id_no

    def _recusar_cascata(self, id_no: str, aresta: ArestaGrafo, papel: PapelAutor) -> ResultadoValidacao:
        """Nomeia a aresta que a remoção do nó levaria junto."""
        return ResultadoValidacao.falha(
            f"Remover '{id_no}' removeria junto a aresta '{aresta.id}' ({aresta.tipo.value}), "
            f"que o papel '{papel.value}' nao pode remover",
            "RoleGate",
            {"id_no": id_no, "id_aresta": aresta.id, "tipo_aresta": aresta.tipo.value},
            modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
        )

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

    def _par_de_tipos(
        self,
        pontas: Sequence[str],
        contexto: ContextoPapel,
    ) -> tuple[TipoNo, TipoNo] | None:
        """Os tipos das duas pontas, lidos do lote projetado; None quando alguma não existe.

        Uma aresta pode ter dono diferente conforme o que liga: `substitui`
        entre Aprendizados é consolidação de memória, e a escreve quem
        registra Aprendizado (kernel/matriz_papeis.py).
        """
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

    def _identificar_tipo(self, item: ItemPatch) -> TipoAresta | None:
        """Lê o tipo declarado no valor da aresta que a operação cria."""
        declarado = item.value.get("tipo") if isinstance(item.value, dict) else None
        return self._converter_tipo(declarado) if declarado is not None else None

    def _converter_tipo(self, declarado: Any) -> TipoAresta | None:
        """Converte o tipo textual, deixando a forma inválida para o SchemaGate."""
        try:
            return TipoAresta(declarado)
        except ValueError:
            return None
