"""Portão 3: Validação de Invariantes de Integridade Relacional do Grafo (Invariant Gate)."""

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado
from graphow.core.ontologia import ARESTAS_DE_CONTENCAO
from graphow.core.types import PapelAutor, StatusQuestion, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import (
    ItemPatch,
    OperacaoPatch,
    PropostaPatch,
    ResultadoValidacao,
)

SEGMENTOS_DE_ELEMENTO_INTEIRO: int = 2

# A aresta que pendura cada tipo, dita na recusa. Os pares valem o que o
# SchemaGate aceita; aqui só se escolhe o que sugerir.
VINCULO_DE_TRABALHO: str = "'produz' vinda de uma Sessao"
VINCULO_ESPERADO: Mapping[TipoNo, str] = {
    TipoNo.SETOR: "'contem' vinda de um Projeto",
    TipoNo.SESSAO: "'contem' vinda de um Setor",
    TipoNo.TASK: "'produz' vinda de uma Sessao ou 'decompoe' vinda de um Goal ou Task",
}


class InvariantGate:
    """Portão de validação de invariantes relacionais do grafo."""

    def validar(
        self,
        proposta: PropostaPatch,
        estado: GrafoEstado,
        locks_ativos: Mapping[str, str] | None = None,
    ) -> ResultadoValidacao:
        """Executa validação de invariantes de ciclo, questões bloqueantes e locks."""
        locks: Mapping[str, str] = locks_ativos or {}
        resultado_lock = self._validar_locks_concorrencia(proposta, locks)
        if not resultado_lock.aprovado:
            return resultado_lock
        resultado_hierarquia = self._validar_nos_na_hierarquia(proposta, estado)
        if not resultado_hierarquia.aprovado:
            return resultado_hierarquia
        resultado_bloqueio = self._validar_bloqueio_questoes(proposta, estado)
        if not resultado_bloqueio.aprovado:
            return resultado_bloqueio
        resultado_posse = self._validar_posse_da_tarefa(proposta, estado, locks)
        if not resultado_posse.aprovado:
            return resultado_posse
        return self._validar_aciclicidade_dependencias(proposta, estado)

    def _validar_nos_na_hierarquia(
        self,
        proposta: PropostaPatch,
        estado: GrafoEstado,
    ) -> ResultadoValidacao:
        """Recusa o nó que nasceria sem pai por contenção.

        Um nó sem `contem`, `produz` ou `decompoe` chegando nele não aparece em
        visão colapsada nenhuma: só a pasta "Fora da hierarquia" o mostra, e
        ninguém a abre. O vínculo precisa vir no mesmo lote que cria o nó —
        em dois pedidos, a falha do segundo deixava o órfão para trás. Projeto
        é a raiz legítima e fica de fora. Vale também para o humano: a regra é
        sobre a forma do grafo, não sobre quem escreve.
        """
        criados = self._nos_criados_sem_ser_raiz(proposta)
        if not criados:
            return ResultadoValidacao.sucesso()
        com_pai = self._destinos_de_contencao(proposta, estado)
        for id_no, tipo in criados.items():
            if id_no not in com_pai:
                return self._recusar_no_fora_da_hierarquia(id_no, tipo)
        return ResultadoValidacao.sucesso()

    def _nos_criados_sem_ser_raiz(self, proposta: PropostaPatch) -> dict[str, TipoNo]:
        """Nós que o lote cria, exceto Projetos, na ordem em que aparecem."""
        criados: dict[str, TipoNo] = {}
        for item in proposta.operacoes:
            segmentos = [seg for seg in item.path.split("/") if seg]
            if item.op != OperacaoPatch.ADD or len(segmentos) != SEGMENTOS_DE_ELEMENTO_INTEIRO:
                continue
            if segmentos[0] != "nos" or not isinstance(item.value, dict):
                continue
            tipo = next((opcao for opcao in TipoNo if opcao.value == item.value.get("tipo")), None)
            if tipo is not None and tipo != TipoNo.PROJETO:
                criados[segmentos[1]] = tipo
        return criados

    def _destinos_de_contencao(self, proposta: PropostaPatch, estado: GrafoEstado) -> set[str]:
        """Ids que recebem aresta de contenção, já no grafo ou criada neste lote."""
        destinos = {
            aresta.destino_id
            for aresta in estado.arestas.values()
            if aresta.tipo in ARESTAS_DE_CONTENCAO
        }
        tipos_de_contencao = {tipo.value for tipo in ARESTAS_DE_CONTENCAO}
        for item in proposta.operacoes:
            if item.op != OperacaoPatch.ADD or not item.path.startswith("/arestas/"):
                continue
            if isinstance(item.value, dict) and item.value.get("tipo") in tipos_de_contencao:
                destinos.add(str(item.value.get("destino_id")))
        return destinos

    def _recusar_no_fora_da_hierarquia(self, id_no: str, tipo: TipoNo) -> ResultadoValidacao:
        """Diz qual aresta falta, para o autor refazer o lote sem adivinhar."""
        return ResultadoValidacao.falha(
            f"No '{id_no}' ({tipo.value}) nasceria fora da hierarquia. "
            f"Crie no mesmo lote a aresta que o pendura: {VINCULO_ESPERADO.get(tipo, VINCULO_DE_TRABALHO)}",
            "InvariantGate",
            {"id_no": id_no, "tipo": tipo.value},
            modo=ModoFalhaMAST.NO_FORA_DA_HIERARQUIA,
        )

    def _validar_posse_da_tarefa(
        self,
        proposta: PropostaPatch,
        estado: GrafoEstado,
        locks: Mapping[str, str],
    ) -> ResultadoValidacao:
        """Exige que o agente detenha o lock da Task cujo status ele quer mover.

        Sem posse, dois executores na mesma Task não colidiam no kernel e o
        segundo sobrescrevia o status do primeiro sem erro. O humano segue fora
        desta regra: ele é o dono do grafo, não um dos escritores paralelos.
        """
        if proposta.papel == PapelAutor.HUMANO:
            return ResultadoValidacao.sucesso()
        for item in proposta.operacoes:
            id_task = self._identificar_task_com_status_alterado(item, estado)
            if id_task is None or locks.get(id_task) == proposta.autor:
                continue
            return self._recusar_por_falta_de_posse(id_task, locks.get(id_task))
        return ResultadoValidacao.sucesso()

    def _recusar_por_falta_de_posse(self, id_task: str, dono: str | None) -> ResultadoValidacao:
        """Explica ao agente como obter a posse antes de mover o status."""
        situacao = f"pertence a '{dono}'" if dono else "nao foi assumida por ninguem"
        return ResultadoValidacao.falha(
            f"Task '{id_task}' {situacao}. Chame 'assumir_tarefa' antes de alterar o status",
            "InvariantGate",
            {"id_task": id_task, "dono_lock": dono or ""},
            modo=ModoFalhaMAST.POSSE_DE_TAREFA_AUSENTE,
        )

    def _identificar_task_com_status_alterado(
        self,
        item: ItemPatch,
        estado: GrafoEstado,
    ) -> str | None:
        """Devolve o id da Task já existente cujo status a operação reescreve."""
        segmentos = [seg for seg in item.path.split("/") if seg]
        if len(segmentos) < SEGMENTOS_DE_ELEMENTO_INTEIRO or segmentos[0] != "nos":
            return None
        no = estado.nos.get(segmentos[1])
        if no is None or no.tipo != TipoNo.TASK:
            return None
        return segmentos[1] if self._escreve_status(item, segmentos) else None

    def _escreve_status(self, item: ItemPatch, segmentos: list[str]) -> bool:
        """Reconhece a escrita de status na propriedade isolada ou no nó inteiro."""
        if segmentos[-1] == "status":
            return True
        if len(segmentos) != SEGMENTOS_DE_ELEMENTO_INTEIRO or not isinstance(item.value, dict):
            return False
        propriedades = item.value.get("propriedades")
        return isinstance(propriedades, dict) and "status" in propriedades

    def _validar_locks_concorrencia(
        self,
        proposta: PropostaPatch,
        locks: Mapping[str, str],
    ) -> ResultadoValidacao:
        """Garante que a Task não está bloqueada para escrita por outro autor."""
        for item in proposta.operacoes:
            segmentos = [s for s in item.path.split("/") if s]
            if len(segmentos) < 2 or segmentos[0] != "nos":
                continue
            id_no = segmentos[1]
            dono_lock = locks.get(id_no)
            if dono_lock is not None and dono_lock != proposta.autor:
                return ResultadoValidacao.falha(
                    f"Nó '{id_no}' está bloqueado para escrita pelo autor '{dono_lock}'",
                    "InvariantGate",
                    {"id_no": id_no, "dono_lock": dono_lock},
                    modo=ModoFalhaMAST.CONFLITO_CONCORRENCIA_LOCK,
                )
        return ResultadoValidacao.sucesso()

    def _validar_bloqueio_questoes(
        self,
        proposta: PropostaPatch,
        estado: GrafoEstado,
    ) -> ResultadoValidacao:
        """Impede que uma Task seja marcada como 'concluido' se tiver Question aberta."""
        for item in proposta.operacoes:
            if not self._eh_fechamento_task(item):
                continue
            id_task = item.path.split("/")[2]
            if self._tem_questao_bloqueante_aberta(id_task, estado):
                return ResultadoValidacao.falha(
                    f"Task '{id_task}' não pode ser concluída pois possui Question aberta bloqueante pendente",
                    "InvariantGate",
                    {"id_task": id_task},
                    modo=ModoFalhaMAST.FECHAMENTO_COM_BLOQUEIO_PENDENTE,
                )
        return ResultadoValidacao.sucesso()

    def _eh_fechamento_task(self, item: ItemPatch) -> bool:
        """Identifica se a operação é a conclusão de uma Task."""
        if item.op not in (OperacaoPatch.ADD, OperacaoPatch.REPLACE):
            return False
        return "status" in item.path and item.value == StatusTask.CONCLUIDO.value

    def _tem_questao_bloqueante_aberta(self, id_task: str, estado: GrafoEstado) -> bool:
        """Verifica se há aresta 'bloqueia' de uma Question aberta para a Task."""
        for aresta in estado.arestas.values():
            if aresta.destino_id != id_task or aresta.tipo != TipoAresta.BLOQUEIA:
                continue
            no_origem = estado.nos.get(aresta.origem_id)
            if no_origem is None or no_origem.tipo != TipoNo.QUESTION:
                continue
            status = no_origem.obter_propriedade("status", StatusQuestion.ABERTA.value)
            if status == StatusQuestion.ABERTA.value:
                return True
        return False

    def _validar_aciclicidade_dependencias(
        self,
        proposta: PropostaPatch,
        estado: GrafoEstado,
    ) -> ResultadoValidacao:
        """Verifica se arestas 'depende_de' propostas criam ciclos no grafo."""
        adjacencias: dict[str, set[str]] = defaultdict(set)
        for aresta in estado.arestas.values():
            if aresta.tipo == TipoAresta.DEPENDE_DE:
                adjacencias[aresta.origem_id].add(aresta.destino_id)
        for item in proposta.operacoes:
            if not self._eh_nova_aresta_dependencia(item):
                continue
            origem = item.value["origem_id"]
            destino = item.value["destino_id"]
            if self._detectar_caminho(destino, origem, adjacencias):
                return ResultadoValidacao.falha(
                    f"Aresta de dependência criaria um ciclo proibido entre '{origem}' e '{destino}'",
                    "InvariantGate",
                    {"origem": origem, "destino": destino},
                    modo=ModoFalhaMAST.CICLO_DEPENDENCIA,
                )
            adjacencias[origem].add(destino)
        return ResultadoValidacao.sucesso()

    def _eh_nova_aresta_dependencia(self, item: ItemPatch) -> bool:
        """Checa se a operação insere aresta do tipo depende_de."""
        if item.op != OperacaoPatch.ADD or not item.path.startswith("/arestas/"):
            return False
        return isinstance(item.value, dict) and item.value.get("tipo") == TipoAresta.DEPENDE_DE.value

    def _detectar_caminho(self, inicio: str, alvo: str, adj: Mapping[str, set[str]]) -> bool:
        """Busca em profundidade (DFS) iterativa para encontrar caminho entre dois nós."""
        if inicio == alvo:
            return True
        visitados: set[str] = set()
        pilha: list[str] = [inicio]
        while pilha:
            atual = pilha.pop()
            if atual == alvo:
                return True
            pilha.extend(self._sucessores_nao_visitados(atual, adj, visitados))
        return False

    def _sucessores_nao_visitados(
        self,
        atual: str,
        adj: Mapping[str, set[str]],
        visitados: set[str],
    ) -> tuple[str, ...]:
        """Marca o nó como visitado e devolve seus sucessores ainda inexplorados."""
        if atual in visitados:
            return ()
        visitados.add(atual)
        return tuple(vizinho for vizinho in adj.get(atual, set()) if vizinho not in visitados)
