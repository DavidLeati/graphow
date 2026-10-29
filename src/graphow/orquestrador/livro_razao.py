"""O livro-razão do Goal, gravado pelo orquestrador com o papel `orquestrador`.

Cada passo do laço vira um lote só, que os quatro portões conferem como
qualquer outro: o Goal e a Sessao que o produz, o plano (critérios como
Criterio, decisões como Decision, fatias como Task com as dependências), o
início e o fim de cada tentativa, a dúvida que pausa uma fatia, o commit como
Artifact, a ponta da branch do Goal e as fatias de correção, que derivam do
Achado que corrigem. A verificação, com os Achados dela, é gravada por
orquestrador/gravacao_da_verificacao.py.
Um lote recusado é defeito do orquestrador, e não do agente: vira erro com o
motivo do kernel, e o laço para.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from graphow.core import aceite as a
from graphow.core.exceptions import GraphowError
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.correcoes import agrupar_o_ciclo, propriedades_da_correcao, titulo_da_correcao
from graphow.orquestrador.leitura_do_goal import AchadoRegistrado, FatiaRegistrada
from graphow.orquestrador.saidas import SaidaDoExecutor
from graphow.projection.graph_view import GrafoView

RAMO_PADRAO: str = "main"
ACAO_DA_REVISAO_DE_RISCO: str = "revisao_de_risco"
ROTULO_DO_SETOR: str = "Goals orquestrados"
LIMITE_DO_ROTULO: int = 120


class LoteRecusado(GraphowError):
    """O kernel recusou um lote do orquestrador: defeito do laço, e não do agente."""


def no(id_no: str, tipo: TipoNo, rotulo: str, *, propriedades: Mapping[str, Any] | None = None) -> ItemPatch:
    """A criação de um nó."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": rotulo[:LIMITE_DO_ROTULO], "propriedades": dict(propriedades or {})}
    return ItemPatch(OperacaoPatch.ADD, f"/nos/{id_no}", valor)


def aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """A criação de uma aresta, com id derivado das pontas."""
    id_aresta = f"{tipo.value}--{origem}--{destino}"
    valor = {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return ItemPatch(OperacaoPatch.ADD, f"/arestas/{id_aresta}", valor)


def propriedade(id_no: str, chave: str, valor: object) -> ItemPatch:
    """A escrita de uma propriedade de um nó que já existe."""
    return ItemPatch(OperacaoPatch.REPLACE, f"/nos/{id_no}/propriedades/{chave}", valor)


@dataclass(frozen=True)
class GoalNovo:
    """O Goal que nasce de uma spec: onde ele mora no grafo e o que ele guarda."""

    id_goal: str
    rotulo: str
    spec: str
    configuracao: m.ConfiguracaoDoGoal
    nome_do_repositorio: str


class LivroRazaoDoGoal:
    """As escritas do laço sobre um Goal, cada uma num lote do papel `orquestrador`."""

    def __init__(self, kernel: WriteKernel, id_goal: str, ramo_id: str = RAMO_PADRAO) -> None:
        self._kernel: WriteKernel = kernel
        self.id_goal: str = id_goal
        self._ramo_id: str = ramo_id

    @property
    def id_sessao(self) -> str:
        """A Sessao do orquestrador que produz o que ele grava do Goal."""
        return m.id_da_sessao(self.id_goal)

    def view(self) -> GrafoView:
        """O grafo agora."""
        return self._kernel.obter_view(self._ramo_id)

    def gravar(self, operacoes: Sequence[ItemPatch], justificativa: str) -> None:
        """Submete o lote; a recusa vira `LoteRecusado` com o motivo do kernel."""
        dados = DadosPropostaPatch(
            autor=m.AUTOR_DO_ORQUESTRADOR, papel=PapelAutor.ORQUESTRADOR, operacoes=tuple(operacoes),
            justificativa=justificativa, ramo_id=self._ramo_id, goal_conduzido=self.id_goal,
        )
        recibo = self._kernel.submeter_patch(PropostaPatch.criar(dados))
        if not recibo.sucesso:
            raise LoteRecusado(
                "o kernel recusou o lote do orquestrador",
                {"lote": justificativa, "motivo": recibo.mensagem, "modo": recibo.modo_de_falha or ""},
            )

    def produzido(self, id_no: str, tipo: TipoNo, rotulo: str, *, propriedades: Mapping[str, Any]) -> list[ItemPatch]:
        """O nó de trabalho pendurado na Sessao do orquestrador."""
        return [no(id_no, tipo, rotulo, propriedades=propriedades), aresta(self.id_sessao, id_no, TipoAresta.PRODUZ)]

    def criar_goal(self, novo: GoalNovo) -> None:
        """Projeto e Setor do repositório (se faltam), a Sessao do Goal e o Goal com a spec e a configuração."""
        slug = m.slug_de(novo.nome_do_repositorio)
        id_projeto, id_setor = m.id_do_projeto(slug), m.id_do_setor(slug)
        view = self.view()
        operacoes: list[ItemPatch] = []
        if not view.contem_no(id_projeto):
            operacoes.append(no(id_projeto, TipoNo.PROJETO, novo.nome_do_repositorio, propriedades={"repositorio": novo.configuracao.repositorio}))
        if not view.contem_no(id_setor):
            operacoes += [no(id_setor, TipoNo.SETOR, ROTULO_DO_SETOR), aresta(id_projeto, id_setor, TipoAresta.CONTEM)]
        propriedades = {
            m.CAMPO_STATUS: m.STATUS_PENDENTE,
            "descricao": f"Goal criado por graphow orquestrar a partir de uma spec ({novo.configuracao.slug}).",
            m.CAMPO_SPEC: novo.spec,
            m.CAMPO_ORQUESTRACAO: novo.configuracao.em_json(),
        }
        operacoes += self._operacoes_da_sessao(id_setor)
        operacoes += self.produzido(self.id_goal, TipoNo.GOAL, novo.rotulo, propriedades=propriedades)
        self.gravar(operacoes, f"Goal {self.id_goal} criado da spec")

    def adotar_goal(self, id_setor: str, spec: str, configuracao: m.ConfiguracaoDoGoal) -> None:
        """O Goal que o gerente criou passa a ser conduzido: a Sessao do orquestrador, a spec montada e a configuração."""
        operacoes = [] if self.view().contem_no(self.id_sessao) else self._operacoes_da_sessao(id_setor)
        operacoes += [
            propriedade(self.id_goal, m.CAMPO_SPEC, spec),
            propriedade(self.id_goal, m.CAMPO_ORQUESTRACAO, configuracao.em_json()),
        ]
        self.gravar(operacoes, f"Goal {self.id_goal} adotado pelo orquestrador")

    def _operacoes_da_sessao(self, id_setor: str) -> list[ItemPatch]:
        """A Sessao do orquestrador, contida no Setor."""
        rotulo = f"Orquestracao de {self.id_goal}"
        return [no(self.id_sessao, TipoNo.SESSAO, rotulo, propriedades={"status": "ativa"}), aresta(id_setor, self.id_sessao, TipoAresta.CONTEM)]

    def gravar_plano_proposto(self, dados: Mapping[str, Any]) -> None:
        """A saída conferida do planejador no Goal, antes de qualquer passo que possa cair no meio."""
        self.gravar([propriedade(self.id_goal, m.CAMPO_PLANO_PROPOSTO, dict(dados))], f"Plano proposto do Goal {self.id_goal}")

    def iniciar_tentativa(self, id_task: str, tentativa: int) -> None:
        """A fatia entra em andamento, com a tentativa contada antes de a sessão abrir."""
        self.gravar(
            [propriedade(id_task, m.CAMPO_STATUS, m.STATUS_EM_ANDAMENTO), propriedade(id_task, m.CAMPO_TENTATIVAS, tentativa)],
            f"Tentativa {tentativa} da fatia {id_task}",
        )

    def guardar_entrega(self, id_task: str, entrega: Mapping[str, Any]) -> None:
        """A entrega pronta do executor fica na fatia (o .patch e a saída): a retomada refaz só a revisão."""
        self.gravar([propriedade(id_task, m.CAMPO_ENTREGA_PENDENTE, dict(entrega))], f"Entrega da fatia {id_task} guardada")

    def devolver_tentativa(self, id_task: str, tentativas: int) -> None:
        """A tentativa que a API recusou não conta: a fatia volta a pendente, com as tentativas de antes dela."""
        self.gravar(
            [propriedade(id_task, m.CAMPO_STATUS, m.STATUS_PENDENTE), propriedade(id_task, m.CAMPO_TENTATIVAS, tentativas)],
            f"Tentativa da fatia {id_task} devolvida: a API recusou a sessao",
        )

    def concluir_fatia(
        self, id_task: str, tentativa: int, *, commit: str, saida: SaidaDoExecutor, observacao: str = "",
        achados: Sequence[str] = (), extra: Sequence[ItemPatch] = (),
    ) -> None:
        """O commit vira Artifact da fatia, e a fatia fecha; a observação diz o que o orquestrador desfez no git.

        Na fatia de correção, os Achados que ela corrige passam a corrigidos no
        mesmo lote: resolvidos, só quando uma conferência os der por corrigidos e
        a verificação do marco sair limpa.
        """
        id_artefato = f"art-{id_task}-t{tentativa}"
        propriedades = {
            m.CAMPO_COMMIT: commit, "arquivos": list(saida.arquivos), "resumo": saida.resumo, "testes": list(saida.testes),
            "observacao": observacao,
        }
        self.gravar(
            [
                *self.produzido(id_artefato, TipoNo.ARTIFACT, f"Commit {commit[:12]} da fatia {id_task}", propriedades=propriedades),
                aresta(id_artefato, id_task, TipoAresta.DERIVA_DE),
                propriedade(id_task, m.CAMPO_COMMIT, commit),
                propriedade(id_task, m.CAMPO_STATUS, m.STATUS_CONCLUIDO),
                propriedade(id_task, m.CAMPO_ENTREGA_PENDENTE, None),
                *extra,
                *(item for achado in achados for item in (propriedade(achado, a.CAMPO_ESTADO, a.ESTADO_CORRIGIDO),
                                                          propriedade(achado, a.CAMPO_COMMIT_DA_CORRECAO, commit))),
            ],
            f"Fatia {id_task} concluida em {commit[:12]}",
        )

    def registrar_falha(self, id_task: str, tentativa: int, *, erro: str, patch: str, falhas: int, nota: bool = True) -> None:
        """A tentativa que falhou vira Note da fatia, e a fatia volta a pendente com o erro e a conta das falhas.

        A rejeição da revisão de risco não vira Note: ela já está nos nós Achado
        da revisão (`nota=False`), e a fatia só ganha o erro e a conta.
        """
        id_nota = f"nota-{id_task}-t{tentativa}"
        propriedades = {"acao": m.ACAO_DA_TENTATIVA, "erro": erro, m.CAMPO_PATCH: patch, m.CAMPO_TENTATIVAS: tentativa}
        rotulo = f"Tentativa {tentativa} de {id_task} falhou"
        self.gravar(
            [
                *(self.produzido(id_nota, TipoNo.NOTE, rotulo, propriedades=propriedades) if nota else []),
                *([aresta(id_nota, id_task, TipoAresta.DERIVA_DE)] if nota else []),
                propriedade(id_task, m.CAMPO_ULTIMO_ERRO, erro),
                propriedade(id_task, m.CAMPO_PATCH, patch),
                propriedade(id_task, m.CAMPO_FALHAS, falhas),
                propriedade(id_task, m.CAMPO_STATUS, m.STATUS_PENDENTE),
                propriedade(id_task, m.CAMPO_ENTREGA_PENDENTE, None),
            ],
            f"Tentativa {tentativa} da fatia {id_task} falhou",
        )

    def registrar_revisao(self, id_task: str, tentativa: int, *, dados: Mapping[str, Any], achados: Sequence[ItemPatch] = ()) -> None:
        """O veredito da revisão da fatia de risco vira Evidence que deriva da fatia, com os Achados dela no mesmo lote."""
        id_evidencia = m.id_da_revisao(id_task, tentativa)
        veredito = str(dados.get("veredito", ""))
        propriedades = {"acao": ACAO_DA_REVISAO_DE_RISCO, m.CAMPO_VEREDITO: veredito, "resumo": str(dados.get("resumo", "")),
                        "problemas": [dict(item) for item in dados.get("problemas", [])], "motivo": str(dados.get("motivo", "")),
                        "observacao": str(dados.get("observacao", "")), m.CAMPO_TENTATIVAS: tentativa}
        self.gravar(
            [*self.produzido(id_evidencia, TipoNo.EVIDENCE, f"Revisao de risco de {id_task}: {veredito}", propriedades=propriedades),
             aresta(id_evidencia, id_task, TipoAresta.DERIVA_DE), *achados],
            f"Revisao de risco da fatia {id_task} na tentativa {tentativa}",
        )

    def marcar_pendencia(self, id_task: str, motivo: str, pendencias: Sequence[Mapping[str, Any]]) -> None:
        """A fatia que falhou duas vezes sai da fila e vira pendência do Goal."""
        self.gravar(
            [
                propriedade(id_task, m.CAMPO_STATUS, m.STATUS_BLOQUEADO),
                propriedade(id_task, m.CAMPO_PENDENCIA, motivo),
                propriedade(self.id_goal, m.CAMPO_PENDENCIAS, [dict(item) for item in pendencias]),
            ],
            f"Fatia {id_task} virou pendencia do Goal",
        )

    def abrir_duvida(self, id_task: str, tentativa: int, *, pergunta: str, patch: str, criterio_do_teste: str = "") -> str:
        """A dúvida do executor vira Question que bloqueia a fatia; devolve o id dela.

        A que diz que o teste de aceite de um critério está errado guarda o
        critério: respondida, ela faz o autor de aceite refazer aquele teste.
        """
        id_questao = f"q-{id_task}-t{tentativa}"
        propriedades = {
            "status": "aberta", m.CAMPO_PERGUNTA: pergunta, m.CAMPO_ABERTA_POR: m.AUTOR_DO_ORQUESTRADOR, m.CAMPO_FATIA: id_task,
            m.CAMPO_CRITERIO_DO_TESTE: criterio_do_teste,
        }
        self.gravar(
            [
                *self.produzido(id_questao, TipoNo.QUESTION, pergunta.splitlines()[0], propriedades=propriedades),
                aresta(id_questao, id_task, TipoAresta.BLOQUEIA),
                propriedade(id_task, m.CAMPO_PATCH, patch),
                propriedade(id_task, m.CAMPO_STATUS, m.STATUS_PENDENTE),
            ],
            f"Duvida do executor pausa a fatia {id_task}",
        )
        return id_questao

    def gravar_ponta(self, ponta: Mapping[str, str]) -> None:
        """A ponta da branch do Goal como o git a tem agora: o commit e o commit do código."""
        commit = str(ponta.get(m.CAMPO_COMMIT, ""))
        self.gravar([propriedade(self.id_goal, m.CAMPO_PONTA_DO_RAMO, dict(ponta))], f"Ponta da branch do Goal {self.id_goal} em {commit[:12]}")

    def criar_correcoes(
        self, id_evidencia: str, achados: Sequence[AchadoRegistrado], *, ciclo: int, ordem: int, marco: str = ""
    ) -> None:
        """Os Achados bloqueantes do ciclo viram uma fatia de correção do marco, que deriva de todos eles.

        O código é `<marco>.K<ciclo>.<n>`; `ciclos_de_correcao` no Goal guarda o
        ciclo das últimas correções abertas (a conta por marco sai das fatias).
        Na bancada, os 8 bloqueantes de um marco viraram 8 sessões de executor;
        agora o ciclo é uma sessão só, e só a final que cobra os outros marcos
        passa do teto e se divide (orquestrador/correcoes.py).
        """
        slug = self.view().obter_no(self.id_goal).obter_propriedade(m.CAMPO_ORQUESTRACAO, {}).get("slug", self.id_goal)
        operacoes: list[ItemPatch] = []
        for indice, grupo in enumerate(agrupar_o_ciclo(achados), start=1):
            codigo = f"{marco}.K{ciclo}.{indice}" if marco else f"K{ciclo}.{indice}"
            id_task = m.id_da_fatia(slug, codigo)
            propriedades = {**propriedades_da_correcao(grupo), m.CAMPO_STATUS: m.STATUS_PENDENTE, m.CAMPO_FATIA: codigo,
                            m.CAMPO_ORDEM: ordem + indice, m.CAMPO_CORRIGE: id_evidencia, m.CAMPO_MARCO: marco, m.CAMPO_TENTATIVAS: 0}
            operacoes += self.produzido(id_task, TipoNo.TASK, titulo_da_correcao(grupo), propriedades=propriedades)
            operacoes.append(aresta(self.id_goal, id_task, TipoAresta.DECOMPOE))
            operacoes += [aresta(id_task, achado.id, TipoAresta.DERIVA_DE) for achado in grupo]
        operacoes.append(propriedade(self.id_goal, m.CAMPO_CICLOS, ciclo))
        self.gravar(operacoes, f"Ciclo {ciclo} de correcao do Goal {self.id_goal}")

    def dividir_correcao(self, fatia: FatiaRegistrada, achados: Sequence[AchadoRegistrado]) -> None:
        """A correção agrupada que esgotou as tentativas sai do plano e vira uma fatia por achado, no mesmo ciclo."""
        slug = self.view().obter_no(self.id_goal).obter_propriedade(m.CAMPO_ORQUESTRACAO, {}).get("slug", self.id_goal)
        operacoes: list[ItemPatch] = [propriedade(fatia.id, m.CAMPO_SUBSTITUIDA, f"divisao-{fatia.id}")]
        for indice, achado in enumerate(achados, start=1):
            codigo = f"{fatia.codigo}.{indice}"
            id_task = m.id_da_fatia(slug, codigo)
            propriedades = {**propriedades_da_correcao((achado,)), m.CAMPO_STATUS: m.STATUS_PENDENTE, m.CAMPO_FATIA: codigo,
                            m.CAMPO_ORDEM: fatia.ordem, m.CAMPO_CORRIGE: fatia.texto(m.CAMPO_CORRIGE),
                            m.CAMPO_MARCO: fatia.texto(m.CAMPO_MARCO), m.CAMPO_TENTATIVAS: 0}
            operacoes += self.produzido(id_task, TipoNo.TASK, titulo_da_correcao((achado,)), propriedades=propriedades)
            operacoes += [aresta(self.id_goal, id_task, TipoAresta.DECOMPOE), aresta(id_task, achado.id, TipoAresta.DERIVA_DE)]
        self.gravar(operacoes, f"Correcao {fatia.codigo} dividida em {len(achados)} fatias, uma por achado")

    def resolver(self, achados: Sequence[str], justificativa: str) -> None:
        """Os Achados corrigidos passam a resolvidos: a conferência os confirmou, e a verificação limpa do marco fecha o ciclo."""
        if achados:
            self.gravar([propriedade(achado, a.CAMPO_ESTADO, a.ESTADO_RESOLVIDO) for achado in achados], justificativa)

    def fechar(self, commit_integrado: str) -> None:
        """O Goal fecha com o commit integrado, e a Sessao do orquestrador se encerra."""
        self.gravar(
            [
                propriedade(self.id_goal, m.CAMPO_INTEGRADO_EM, commit_integrado),
                propriedade(self.id_goal, m.CAMPO_STATUS, m.STATUS_CONCLUIDO),
                propriedade(self.id_sessao, "status", "concluida"),
            ],
            f"Goal {self.id_goal} fechado em {commit_integrado[:12]}",
        )
