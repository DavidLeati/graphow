"""O caso 14 para 121 da seção 2, montado pelos portões reais: a expansão lateral que o K pega antes da execução.

O Goal tem um plano humano de 14 Tasks, um critério de aceite e uma fronteira. Uma
Decision do planejador, motivada pela regra que o humano respondeu, gera 9 Tasks
emergentes (B3) para 4 alvos fora da fronteira, entremeadas de subdivisões
legítimas do plano. Tudo passa pelo `submeter_patch` do kernel em memória: o humano
aprova o plano e cria as Constraints, o planejador cria Decision e Tasks com as
ligações que o kernel confere. Mede onde o K dispara, o que a fila serve antes e o
que o teto de expansão faz com a sexta emergente.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from graphow.context.escopo_do_goal import limiares_do_goal, placar_do_goal
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.governanca import ID_GOVERNANCA_GLOBAL
from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel
from graphow.projection.fila_trabalho import PRIORIDADE_POR_STATUS, FilaDeTrabalho, TarefaExecutavel
from graphow.projection.placar_escopo import LimiaresDeDesvio, PlacarDeEscopo

ID_PROJETO: str = "proj"
ID_SETOR: str = "setor"
ID_SESSAO: str = "sess"
ID_GOAL: str = "goal"
ID_CRITERIO: str = "c-criterio"
ID_FRONTEIRA: str = "c-fronteira"
ID_QUESTAO: str = "q-regra"
ID_DECISAO: str = "dec-regra"
AUTOR_HUMANO: str = "david"
AUTOR_PLANEJADOR: str = "planejador-1"
TASKS_DO_PLANO: int = 14
FASES_DO_PLANO: int = 5
EMERGENTES: int = 9
SUBDIVISOES: int = 5
ALVOS_FORA_DA_FRONTEIRA: tuple[str, ...] = (
    "servico_cobranca/regra.py",
    "servico_relatorios/regra.py",
    "servico_notificacoes/regra.py",
    "servico_auditoria/regra.py",
)
TETO_DO_CENARIO: int = 5


@dataclass(frozen=True)
class ResultadoDoTeto:
    """O que o teto de expansão fez com as emergentes: quantas passaram, o que recusou e se um desvio respondido reabre."""

    teto: int
    aceitas_antes_da_recusa: int
    recusada: str
    modo_de_falha: str | None
    aceita_depois_da_resposta: bool
    lote_inteiro_recusado: bool


@dataclass(frozen=True)
class ResultadoDaExpansaoLateral:
    """As medidas do cenário: o K, a antecedência, a fila antiga contra a nova, a recusa sem ligação e o teto."""

    tasks_do_plano: int
    subdivisoes: int
    emergentes: int
    alvos_da_raiz: tuple[str, ...]
    contador_k_por_emergente: tuple[int, ...]
    k_dispara_na_emergente: int | None
    contador_m_por_emergente: tuple[int, ...]
    m_dispara_na_emergente: int | None
    raizes_sem_veredito: tuple[str, ...]
    tasks_iniciadas_no_alerta: int
    fila_antiga: tuple[str, ...]
    fila_nova: tuple[str, ...]
    sem_ligacao_recusada: str | None
    teto: ResultadoDoTeto

    def posicao_do_plano(self) -> tuple[int, int]:
        """A posição (de 1) da primeira Task do plano na fila antiga e na nova."""
        return _posicao(self.fila_antiga, "plano-"), _posicao(self.fila_nova, "plano-")

    def posicao_da_primeira_emergente(self) -> tuple[int, int]:
        """A posição (de 1) da primeira Task emergente na fila antiga e na nova."""
        return _posicao(self.fila_antiga, "expansao-"), _posicao(self.fila_nova, "expansao-")

    def emergentes_a_frente_do_plano(self) -> tuple[int, int]:
        """Quantas emergentes a fila antiga e a nova servem antes da primeira Task do plano."""
        antiga, nova = self.posicao_do_plano()
        return _antes_de(self.fila_antiga, antiga, "expansao-"), _antes_de(self.fila_nova, nova, "expansao-")


def medir_expansao_lateral() -> ResultadoDaExpansaoLateral:
    """Monta o cenário sem teto, mede o K e a fila, e repete com o teto ligado."""
    cenario = _Cenario()
    cenario.criar_subdivisoes(3)
    contadores = tuple(cenario.criar_emergente(n) for n in range(1, EMERGENTES + 1))
    k_por_emergente, m_por_emergente = tuple(c[0] for c in contadores), tuple(c[1] for c in contadores)
    cenario.criar_subdivisoes(SUBDIVISOES - 3, a_partir_de=4)
    view = cenario.kernel.obter_view()
    fila = FilaDeTrabalho(view).proximas_tarefas(ID_SESSAO)
    placar = cenario.placar()
    return ResultadoDaExpansaoLateral(
        tasks_do_plano=TASKS_DO_PLANO,
        subdivisoes=SUBDIVISOES,
        emergentes=EMERGENTES,
        alvos_da_raiz=_alvos_da_raiz(placar),
        contador_k_por_emergente=k_por_emergente,
        k_dispara_na_emergente=_primeira_acima(k_por_emergente, cenario.limiares.por_raiz),
        contador_m_por_emergente=m_por_emergente,
        m_dispara_na_emergente=_primeira_acima(m_por_emergente, cenario.limiares.por_goal),
        raizes_sem_veredito=placar.sem_veredito,
        tasks_iniciadas_no_alerta=cenario.iniciadas_ate_o_alerta,
        fila_antiga=tuple(t.id for t in sorted(fila, key=_chave_antiga)),
        fila_nova=tuple(t.id for t in fila),
        sem_ligacao_recusada=_recusa_sem_ligacao(),
        teto=_medir_teto(),
    )


def _primeira_acima(contadores: Sequence[int], limiar: int) -> int | None:
    """O número (de 1) da primeira emergente em que o contador passa do limiar; None se nunca passa."""
    return next((numero for numero, contador in enumerate(contadores, start=1) if contador > limiar), None)


def _chave_antiga(tarefa: TarefaExecutavel) -> tuple[int, str]:
    """A ordem de antes do escopo governado: status e depois identificador."""
    return PRIORIDADE_POR_STATUS[tarefa.status], tarefa.id


def _posicao(fila: Sequence[str], prefixo: str) -> int:
    """A posição (de 1) do primeiro id com o prefixo."""
    return next(indice for indice, id_task in enumerate(fila, start=1) if id_task.startswith(prefixo))


def _antes_de(fila: Sequence[str], posicao: int, prefixo: str) -> int:
    """Quantos ids com o prefixo vêm antes da posição (de 1)."""
    return sum(1 for id_task in fila[: posicao - 1] if id_task.startswith(prefixo))


def _alvos_da_raiz(placar: PlacarDeEscopo) -> tuple[str, ...]:
    """Os alvos tocados pelas Tasks da raiz que mais gerou."""
    raiz = placar.raiz_que_mais_gerou
    return raiz.custo.alvos if raiz is not None else ()


def _recusa_sem_ligacao() -> str | None:
    """O modo de falha com que o kernel recusa a Task do planejador que nasce sob o plano sem ligação."""
    cenario = _Cenario()
    recibo = cenario.submeter(PapelAutor.PLANEJADOR, *_operacoes_da_task("solta", pai=ID_GOAL))
    return None if recibo.sucesso else recibo.modo_de_falha


def _medir_teto() -> ResultadoDoTeto:
    """As emergentes sob `teto_expansao` 5: uma a uma e em lote, com a resposta de desvio do humano no meio."""
    cenario = _Cenario(teto=TETO_DO_CENARIO)
    recibos = [cenario.tentar_emergente(n) for n in range(1, EMERGENTES + 1)]
    aceitas = sum(1 for recibo in recibos if recibo.sucesso)
    recusa = next(recibo for recibo in recibos if not recibo.sucesso)
    cenario.responder_desvio()
    reaberto = cenario.tentar_emergente(EMERGENTES + 1)
    return ResultadoDoTeto(
        teto=TETO_DO_CENARIO,
        aceitas_antes_da_recusa=aceitas,
        recusada=_id_recusado(recusa),
        modo_de_falha=recusa.modo_de_falha,
        aceita_depois_da_resposta=reaberto.sucesso,
        lote_inteiro_recusado=_lote_inteiro_e_recusado(),
    )


def _id_recusado(recibo: ResultadoSubmissao) -> str:
    """O id da Task que a mensagem de recusa do teto nomeia."""
    return recibo.mensagem.split("'")[1] if "'" in recibo.mensagem else ""


def _lote_inteiro_e_recusado() -> bool:
    """As 9 emergentes num lote só passam do teto: o lote cai inteiro, sem deixar nenhuma."""
    cenario = _Cenario(teto=TETO_DO_CENARIO)
    operacoes = tuple(op for n in range(1, EMERGENTES + 1) for op in _operacoes_da_emergente(n))
    recibo = cenario.submeter(PapelAutor.PLANEJADOR, *operacoes)
    criadas = [id_no for id_no in cenario.kernel.obter_estado().nos if id_no.startswith("expansao-")]
    return (not recibo.sucesso) and recibo.modo_de_falha == ModoFalhaMAST.ORCAMENTO_DE_ESCOPO_ESGOTADO.value and not criadas


class _Cenario:
    """O Goal com plano humano aprovado e a Decision do planejador pronta, sobre um kernel em memória."""

    def __init__(self, teto: int = 0) -> None:
        self.kernel: WriteKernel = montar_kernel_em_memoria()
        self.iniciadas_ate_o_alerta: int = 0
        self._teto: int = teto
        self._montar_terreno()
        self._aprovar_plano()
        self._criar_decisao()

    @property
    def limiares(self) -> LimiaresDeDesvio:
        """K e M da política vigente."""
        return limiares_do_goal(self.kernel.obter_view(), ID_GOAL)

    def submeter(self, papel: PapelAutor, *operacoes: ItemPatch) -> ResultadoSubmissao:
        """Submete o lote sob o papel, com o autor do cenário para ele."""
        autor = AUTOR_HUMANO if papel == PapelAutor.HUMANO else AUTOR_PLANEJADOR
        dados = DadosPropostaPatch(autor=autor, papel=papel, operacoes=operacoes, justificativa="cenario")
        return self.kernel.submeter_patch(PropostaPatch.criar(dados))

    def placar(self) -> PlacarDeEscopo:
        """O placar do Goal com os limiares da política."""
        return placar_do_goal(self.kernel.obter_view(), ID_GOAL)

    def tentar_emergente(self, numero: int) -> ResultadoSubmissao:
        """O planejador tenta criar a emergente `numero`."""
        return self.submeter(PapelAutor.PLANEJADOR, *_operacoes_da_emergente(numero))

    def criar_emergente(self, numero: int) -> tuple[int, int]:
        """Cria a emergente e devolve os contadores de K (da raiz) e de M (do Goal), lidos do placar logo depois."""
        assert self.tentar_emergente(numero).sucesso
        placar = self.placar()
        raiz = next(r for r in placar.raizes if r.raiz == ID_QUESTAO)
        if raiz.passou_de_k and not self.iniciadas_ate_o_alerta:
            self.iniciadas_ate_o_alerta = self._iniciadas()
        return raiz.contador_k, placar.emergentes_para_m

    def criar_subdivisoes(self, quantas: int, a_partir_de: int = 1) -> None:
        """O planejador subdivide Tasks do plano, o que o kernel aceita sem critério."""
        for numero in range(a_partir_de, a_partir_de + quantas):
            pai = f"plano-{numero:02d}"
            recibo = self.submeter(PapelAutor.PLANEJADOR, *_operacoes_da_task(f"subdiv-{numero:02d}", pai=pai))
            assert recibo.sucesso, recibo.mensagem

    def responder_desvio(self) -> None:
        """O humano responde ao placar do Goal inteiro: zera K e M e reabre o teto."""
        estado = self.kernel.obter_estado()
        entrada = {
            "seq": estado.versao_log,
            "respondido_por": AUTOR_HUMANO,
            "papel": PapelAutor.HUMANO.value,
            "raiz": None,
            "resposta": "seguir",
        }
        anteriores = list(estado.nos[ID_GOAL].propriedades.get("respostas_de_desvio") or [])
        recibo = self.submeter(PapelAutor.HUMANO, _definir(ID_GOAL, "respostas_de_desvio", [*anteriores, entrada]))
        assert recibo.sucesso, recibo.mensagem

    def _iniciadas(self) -> int:
        """Quantas Tasks já saíram de `pendente`."""
        nos = self.kernel.obter_estado().nos.values()
        return sum(1 for no in nos if no.tipo == TipoNo.TASK and no.propriedades.get("status") != StatusTask.PENDENTE.value)

    def _montar_terreno(self) -> None:
        """O humano cria o Projeto, o Goal, as Constraints, a Question respondida, o plano de 14 Tasks e, se pedido, o teto."""
        operacoes = [
            *_no_produzido(ID_PROJETO, TipoNo.PROJETO, produtor=None),
            *_no_produzido(ID_SETOR, TipoNo.SETOR, produtor=None),
            _aresta(ID_PROJETO, ID_SETOR, TipoAresta.CONTEM),
            *_no_produzido(ID_SESSAO, TipoNo.SESSAO, produtor=None),
            _aresta(ID_SETOR, ID_SESSAO, TipoAresta.CONTEM),
            *_no_produzido(ID_GOAL, TipoNo.GOAL, status="em_andamento"),
            *_constraints(),
            *_no_produzido(ID_QUESTAO, TipoNo.QUESTION, status="respondida"),
            *(op for n in range(1, TASKS_DO_PLANO + 1) for op in _operacoes_do_plano(n)),
            *_governanca(self._teto),
        ]
        recibo = self.submeter(PapelAutor.HUMANO, *operacoes)
        assert recibo.sucesso, recibo.mensagem

    def _aprovar_plano(self) -> None:
        """O humano aprova o plano no `seq` de agora: a partir daqui toda Task nova precisa de ligação."""
        entrada = {"versao": 1, "seq": self.kernel.obter_estado().versao_log, "aprovado_por": AUTOR_HUMANO, "papel": "humano"}
        recibo = self.submeter(PapelAutor.HUMANO, _definir(ID_GOAL, "planos", [entrada]))
        assert recibo.sucesso, recibo.mensagem

    def _criar_decisao(self) -> None:
        """O planejador registra a Decision que orienta o Goal, motivada pela Question que o humano respondeu."""
        operacoes = (
            *_no_produzido(ID_DECISAO, TipoNo.DECISION, produtor=ID_SESSAO),
            _aresta(ID_DECISAO, ID_QUESTAO, TipoAresta.MOTIVADA_POR),
            _aresta(ID_DECISAO, ID_GOAL, TipoAresta.ORIENTA),
        )
        recibo = self.submeter(PapelAutor.PLANEJADOR, *operacoes)
        assert recibo.sucesso, recibo.mensagem


def _operacoes_da_emergente(numero: int) -> tuple[ItemPatch, ...]:
    """A Task B3: motivada pela Decision, atendendo o critério do Goal e tocando um alvo fora da fronteira."""
    id_task = f"expansao-{numero:02d}"
    alvo = ALVOS_FORA_DA_FRONTEIRA[(numero - 1) % len(ALVOS_FORA_DA_FRONTEIRA)]
    return (
        *_operacoes_da_task(id_task, pai=ID_GOAL, arquivos_alvo=[alvo], atende_criterio=[ID_CRITERIO]),
        _aresta(id_task, ID_DECISAO, TipoAresta.MOTIVADA_POR),
    )


def _operacoes_do_plano(numero: int) -> tuple[ItemPatch, ...]:
    """Uma Task do plano humano, de uma das cinco fases, dentro da fronteira."""
    fase = f"fase-{(numero - 1) * FASES_DO_PLANO // TASKS_DO_PLANO + 1}"
    return _operacoes_da_task(f"plano-{numero:02d}", pai=ID_GOAL, fase=fase, arquivos_alvo=[f"modulo/parte_{numero:02d}.py"])


def _operacoes_da_task(id_task: str, *, pai: str, **propriedades: Any) -> tuple[ItemPatch, ...]:
    """Cria a Task `pendente`, produzida pela Sessão e decomposta do pai (o Goal ou uma Task do plano)."""
    return (
        *_no_produzido(id_task, TipoNo.TASK, produtor=ID_SESSAO, status="pendente", **propriedades),
        _aresta(pai, id_task, TipoAresta.DECOMPOE),
    )


def _constraints() -> tuple[ItemPatch, ...]:
    """O critério de aceite e a fronteira, ambos escopando o Goal."""
    return (
        *_no_produzido(ID_CRITERIO, TipoNo.CONSTRAINT, tipo="criterio_aceite"),
        _aresta(ID_CRITERIO, ID_GOAL, TipoAresta.ESCOPA),
        *_no_produzido(ID_FRONTEIRA, TipoNo.CONSTRAINT, tipo="fronteira"),
        _aresta(ID_FRONTEIRA, ID_GOAL, TipoAresta.ESCOPA),
    )


def _governanca(teto: int) -> tuple[ItemPatch, ...]:
    """A política global personalizada com o teto, ou nada quando o teto está desligado."""
    if teto <= 0:
        return ()
    valor = {"id": ID_GOVERNANCA_GLOBAL, "tipo": TipoNo.GOVERNANCA.value, "rotulo": ID_GOVERNANCA_GLOBAL}
    valor["propriedades"] = {"preset": "personalizada", "personalizada": {"teto_expansao": teto}}  # type: ignore[assignment]
    return (ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{ID_GOVERNANCA_GLOBAL}", value=valor),)


def _no_produzido(
    id_no: str, tipo_do_no: TipoNo, *, produtor: str | None = ID_SESSAO, **propriedades: Any
) -> tuple[ItemPatch, ...]:
    """Cria o nó e, se há produtor, a aresta `produz` que o liga à Sessão."""
    valor: dict[str, Any] = {"id": id_no, "tipo": tipo_do_no.value, "rotulo": id_no, "propriedades": propriedades}
    criar = ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)
    if produtor is None:
        return (criar,)
    return (criar, _aresta(produtor, id_no, TipoAresta.PRODUZ))


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Cria a aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    valor = {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=valor)


def _definir(id_no: str, chave: str, valor: Any) -> ItemPatch:
    """Escreve a propriedade inteira do nó."""
    return ItemPatch(op=OperacaoPatch.REPLACE, path=f"/nos/{id_no}/propriedades/{chave}", value=valor)
