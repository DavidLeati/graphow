"""O livro-razão do Goal, gravado pelo orquestrador com o papel `orquestrador`.

Cada passo do laço vira um lote só, que os quatro portões conferem como
qualquer outro: o Goal e a Sessao que o produz, o plano (critérios como
Constraint, decisões como Decision, fatias como Task com as dependências), o
início e o fim de cada tentativa, a dúvida que pausa uma fatia, o commit como
Artifact, a verificação como Evidence ligada ao Goal e as fatias de correção.
Um lote recusado é defeito do orquestrador, e não do agente: vira erro com o
motivo do kernel, e o laço para.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from graphow.core.exceptions import GraphowError
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.saidas import Achado, SaidaDoExecutor, Verificacao
from graphow.orquestrador.suite import LIMITE_DO_TRECHO, ResultadoDaSuite
from graphow.projection.graph_view import GrafoView

RAMO_PADRAO: str = "main"
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
            justificativa=justificativa, ramo_id=self._ramo_id,
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

    def concluir_fatia(self, id_task: str, tentativa: int, *, commit: str, saida: SaidaDoExecutor, observacao: str = "") -> None:
        """O commit vira Artifact da fatia, e a fatia fecha; a observação diz o que o orquestrador desfez no git."""
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
            ],
            f"Fatia {id_task} concluida em {commit[:12]}",
        )

    def registrar_falha(self, id_task: str, tentativa: int, *, erro: str, patch: str, falhas: int) -> None:
        """A tentativa que falhou vira Note da fatia, e a fatia volta a pendente com o erro e a conta das falhas."""
        id_nota = f"nota-{id_task}-t{tentativa}"
        propriedades = {"acao": m.ACAO_DA_TENTATIVA, "erro": erro, m.CAMPO_PATCH: patch, m.CAMPO_TENTATIVAS: tentativa}
        self.gravar(
            [
                *self.produzido(id_nota, TipoNo.NOTE, f"Tentativa {tentativa} de {id_task} falhou", propriedades=propriedades),
                aresta(id_nota, id_task, TipoAresta.DERIVA_DE),
                propriedade(id_task, m.CAMPO_ULTIMO_ERRO, erro),
                propriedade(id_task, m.CAMPO_PATCH, patch),
                propriedade(id_task, m.CAMPO_FALHAS, falhas),
                propriedade(id_task, m.CAMPO_STATUS, m.STATUS_PENDENTE),
            ],
            f"Tentativa {tentativa} da fatia {id_task} falhou",
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

    def abrir_duvida(self, id_task: str, tentativa: int, *, pergunta: str, patch: str) -> str:
        """A dúvida do executor vira Question que bloqueia a fatia; devolve o id dela."""
        id_questao = f"q-{id_task}-t{tentativa}"
        propriedades = {
            "status": "aberta", m.CAMPO_PERGUNTA: pergunta, m.CAMPO_ABERTA_POR: m.AUTOR_DO_ORQUESTRADOR, m.CAMPO_FATIA: id_task,
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

    def gravar_verificacao(
        self, numero: int, verificacao: Verificacao, *, commit: str, ciclo: int, pendencias: Sequence[Mapping[str, Any]],
        suite: ResultadoDaSuite,
    ) -> str:
        """A verificação vira Evidence ligada ao Goal, com os comandos do verificador e a suíte que o orquestrador
        rodou no commit verificado, no mesmo lote da lista de pendências que ela deixa; devolve o id."""
        id_evidencia = f"ver-{self.id_goal}-{numero}"
        bloqueantes = verificacao.bloqueantes()
        propriedades = {
            "acao": m.ACAO_DA_VERIFICACAO,
            m.CAMPO_VEREDITO: m.VEREDITO_COM_BLOQUEANTE if bloqueantes else m.VEREDITO_LIMPO,
            m.CAMPO_COMMIT: commit,
            m.CAMPO_CICLO: ciclo,
            "fonte": "graphow orquestrar: sessao do verificador",
            "resumo": verificacao.resumo,
            "comandos": [comando.em_json() for comando in verificacao.comandos],
            "suite_do_orquestrador": {"comando": suite.comando, "shell": suite.shell, "codigo": suite.codigo, "passou": suite.passou,
                                      "tempo_esgotado": suite.tempo_esgotado, "saida": suite.saida[-LIMITE_DO_TRECHO:]},
            "pareceres": [{"id": p.id, "veredito": p.veredito, "prova": p.prova} for p in (*verificacao.criterios, *verificacao.decisoes)],
            "bloqueantes": [achado.em_json() for achado in bloqueantes],
            "acompanhamentos": [achado.em_json() for achado in verificacao.acompanhamentos()],
        }
        rotulo = f"Verificacao {numero} em {commit[:12]}: " + (f"{len(bloqueantes)} bloqueante(s)" if bloqueantes else "limpa")
        self.gravar(
            [*self.produzido(id_evidencia, TipoNo.EVIDENCE, rotulo, propriedades=propriedades),
             aresta(id_evidencia, self.id_goal, TipoAresta.DERIVA_DE),
             propriedade(self.id_goal, m.CAMPO_PENDENCIAS, [dict(item) for item in pendencias])],
            f"Verificacao {numero} do Goal {self.id_goal}",
        )
        return id_evidencia

    def criar_correcoes(self, id_evidencia: str, achados: Sequence[Achado], *, ciclo: int, ordem: int) -> None:
        """Cada bloqueante vira uma fatia de correção, que diz por `corrige` de que verificação nasceu."""
        slug = self.view().obter_no(self.id_goal).obter_propriedade(m.CAMPO_ORQUESTRACAO, {}).get("slug", self.id_goal)
        operacoes: list[ItemPatch] = []
        for indice, achado in enumerate(achados, start=1):
            codigo = f"K{ciclo}.{indice}"
            id_task = m.id_da_fatia(slug, codigo)
            propriedades = {
                m.CAMPO_STATUS: m.STATUS_PENDENTE, m.CAMPO_FATIA: codigo, m.CAMPO_ORDEM: ordem + indice,
                m.CAMPO_OBJETIVO: f"{achado.descricao}" + (f" (local: {achado.local})" if achado.local else ""),
                m.CAMPO_CRITERIOS: list(achado.criterios), m.CAMPO_ARQUIVOS_ALVO: [achado.local.split(":")[0]] if achado.local else [],
                m.CAMPO_CORRIGE: id_evidencia, m.CAMPO_TENTATIVAS: 0,
            }
            operacoes += self.produzido(id_task, TipoNo.TASK, f"Corrige: {achado.titulo}", propriedades=propriedades)
            operacoes.append(aresta(self.id_goal, id_task, TipoAresta.DECOMPOE))
        operacoes.append(propriedade(self.id_goal, m.CAMPO_CICLOS, ciclo))
        self.gravar(operacoes, f"Ciclo {ciclo} de correcao do Goal {self.id_goal}")

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
