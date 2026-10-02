"""Permissão por papel na camada de arestas: quem cria e remove cada aresta, conforme o que ela liga.

A camada de arestas retornava sucesso para qualquer papel e deixava um
executor reescopar a própria tarefa. Aqui o RoleGate consulta a matriz de
donos (kernel/matriz_papeis.py) para a operação e o papel correntes, amplia os
donos quando a política de governança do projeto tem `estrutura: ilimitado` e,
quando o par de tipos das pontas tem entrada própria, deixa o par prevalecer:
`substitui` entre Aprendizados é consolidação de memória, e a escreve quem
registra Aprendizado.

Três tipos de aresta têm também um gesto de governança (`gesto_da_aresta`): se a
tabela recusa o papel, a política do projeto das pontas pode aceitá-lo, e é
assim que o árbitro retira um `bloqueia`, escopa uma Constraint ou promove um
Aprendizado. A política é lida só do estado do grafo, então o replay do log
repete o veredito.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import ArestaGrafo, GrafoEstado
from graphow.core.ontologia import ARESTAS_DE_CONTENCAO
from graphow.core.governanca import Gesto, PoliticaGovernanca
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.matriz_papeis import (
    DonosDeAresta,
    eh_autoria_propria,
    gesto_da_aresta,
    obter_donos_de_aresta,
    obter_donos_sob_autonomia_ilimitada,
)
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch, PropostaPatch, ResultadoValidacao
from graphow.kernel.politica_governanca import resolver_politica_do_no
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


def descrever_reserva_do_gesto(gesto: Gesto, politica: PoliticaGovernanca) -> str:
    """Diz de quem é o gesto na política do projeto, para a recusa nomear o que falta."""
    return f"A politica de governanca do projeto reserva o gesto '{gesto.value}' ao {politica.valor(gesto)}"


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
        pontas = self._pontas_declaradas(item)
        par = self._par_de_tipos(pontas, contexto)
        donos = self._donos_aplicaveis(tipo, item, contexto, par=par)
        if donos.autoriza(contexto.proposta.papel, False):
            return ResultadoValidacao.sucesso()
        gesto = gesto_da_aresta(tipo, par, False)
        politica = self._politica_que_nega(gesto, pontas, contexto) if gesto is not None else None
        if gesto is not None and politica is None:
            return self._barrar_autoconflito_na_promocao(tipo, pontas, contexto)
        return self._recusar(tipo, contexto.proposta.papel, False, par=par, gesto=gesto, politica=politica)

    def _barrar_autoconflito_na_promocao(
        self,
        tipo: TipoAresta,
        pontas: Sequence[str],
        contexto: ContextoPapel,
    ) -> ResultadoValidacao:
        """O árbitro não promove o Aprendizado que ele mesmo registrou.

        A autoria vem da proveniência do nó (quem o escreveu), comparada sem o
        sufixo de conexão. Um Aprendizado criado no próprio lote ainda não está
        no estado: o autor dele é quem propõe, e o lote é recusado.
        """
        if tipo != TipoAresta.VALE_PARA or not pontas:
            return ResultadoValidacao.sucesso()
        aprendizado = contexto.estado_com_lote.nos.get(pontas[0])
        if aprendizado is None or aprendizado.tipo != TipoNo.APRENDIZADO:
            return ResultadoValidacao.sucesso()
        registrado = contexto.estado.nos.get(aprendizado.id)
        if registrado is not None and not eh_autoria_propria(contexto.proposta.autor, registrado.proveniencia.autor):
            return ResultadoValidacao.sucesso()
        return ResultadoValidacao.falha(
            f"Papel '{contexto.proposta.papel.value}' nao pode promover o Aprendizado '{aprendizado.id}': "
            "foi ele quem o registrou, e promover o proprio aprendizado seria julgar em causa propria",
            "RoleGate",
            {"id_aprendizado": aprendizado.id},
            modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
        )

    def validar_remocao(self, aresta: ArestaGrafo, contexto: ContextoPapel) -> ResultadoValidacao:
        """Julga a remoção pela aresta como ela está no grafo, nunca pelo valor enviado.

        O tipo e as pontas vinham do `value` da operação quando ele trazia
        algum: um executor removia a `bloqueia` que o travava declarando
        `"tipo": "justifica"`, e concluía a Task no lote seguinte. A aresta
        criada antes, no mesmo lote, conta como existente: a antevisão do lote
        a inclui. Remover não é ampliado pela autonomia do projeto.
        """
        pontas = (aresta.origem_id, aresta.destino_id)
        par = self._par_de_tipos(pontas, contexto)
        if obter_donos_de_aresta(aresta.tipo, par).autoriza(contexto.proposta.papel, True):
            return ResultadoValidacao.sucesso()
        gesto = gesto_da_aresta(aresta.tipo, par, True)
        politica = self._politica_que_nega(gesto, pontas, contexto) if gesto is not None else None
        if gesto is None or politica is not None:
            return self._recusar(
                aresta.tipo, contexto.proposta.papel, True, par=par, gesto=gesto, politica=politica
            )
        return self._barrar_autoconflito_no_bloqueio(aresta, contexto)

    def _barrar_autoconflito_no_bloqueio(self, aresta: ArestaGrafo, contexto: ContextoPapel) -> ResultadoValidacao:
        """O árbitro não retira o `bloqueia` de uma Question que ele mesmo abriu.

        Retirar o bloqueio é encerrar a dúvida, e quem a abriu não a julga.
        """
        if aresta.tipo != TipoAresta.BLOQUEIA:
            return ResultadoValidacao.sucesso()
        questao = contexto.estado_com_lote.nos.get(aresta.origem_id)
        if questao is None or not eh_autoria_propria(
            contexto.proposta.autor, questao.propriedades.get("aberta_por")
        ):
            return ResultadoValidacao.sucesso()
        return ResultadoValidacao.falha(
            f"Papel '{contexto.proposta.papel.value}' nao pode remover a aresta 'bloqueia' da Question "
            f"'{questao.id}': foi ele quem a abriu, e encerrar a propria duvida seria julgar em causa propria",
            "RoleGate",
            {"id_questao": questao.id, "id_aresta": aresta.id},
            modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
        )

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
        """Amplia os donos quando a política do projeto da aresta tem estrutura ilimitada.

        Sem isto a autonomia ilimitada voltaria a ser inerte por outro
        caminho: o agente criaria o nó Setor e seria barrado na aresta
        `contem` que o prende ao Projeto.
        """
        if not self._sob_autonomia_ilimitada(item, contexto):
            return obter_donos_de_aresta(tipo, par)
        return obter_donos_sob_autonomia_ilimitada(tipo, par)

    def _sob_autonomia_ilimitada(self, item: ItemPatch, contexto: ContextoPapel) -> bool:
        """Lê a estrutura da política do projeto de cada ponta declarada: basta uma ilimitada."""
        return any(
            resolver_politica_do_no(id_ponta, contexto.estado_com_lote, self._rastreador).estrutura_ilimitada
            for id_ponta in self._pontas_declaradas(item)
        )

    def _politica_que_nega(
        self,
        gesto: Gesto,
        pontas: Sequence[str],
        contexto: ContextoPapel,
    ) -> PoliticaGovernanca | None:
        """A primeira política, entre as dos projetos das pontas, que não entrega o gesto ao papel.

        None quer dizer que todas o entregam. Exigir todas é o lado seguro: uma
        aresta entre dois projetos só passa se nenhum deles reserva o gesto.
        Sem ponta no grafo vale a política global.
        """
        estado = contexto.estado_com_lote
        existentes = [id_ponta for id_ponta in pontas if id_ponta in estado.nos]
        politicas = [resolver_politica_do_no(id_ponta, estado, self._rastreador) for id_ponta in existentes]
        if not politicas:
            politicas = [resolver_politica_do_no("", estado, self._rastreador)]
        for politica in politicas:
            if not politica.permite(gesto, contexto.proposta.papel):
                return politica
        return None

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
        gesto: Gesto | None = None,
        politica: PoliticaGovernanca | None = None,
    ) -> ResultadoValidacao:
        """Explica ao agente quem detém a aresta que ele tentou mexer."""
        verbo = "remover" if eh_remocao else "criar"
        donos = obter_donos_de_aresta(tipo, par)
        autorizados = sorted(p.value for p in (donos.remocao if eh_remocao else donos.adicao))
        reserva = f". {descrever_reserva_do_gesto(gesto, politica)}" if gesto and politica else ""
        return ResultadoValidacao.falha(
            f"Papel '{papel.value}' não pode {verbo} aresta '{tipo.value}'{reserva}",
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
