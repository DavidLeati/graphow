"""Agregação e formatação do relatório de avaliação de tokens por tarefa.

O relatório declara os próprios limites junto do número. A afirmação de "redução
drástica no consumo de tokens" do ADR-0001 nasceu de um paper sem replicação e
nunca teve medição própria; a correção não é publicar outro número sem ressalva.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from graphow.avaliacao.entre_projetos import RelatorioEntreProjetos
from graphow.avaliacao.medicao import MedicaoDaTarefa
from graphow.avaliacao.retomada import MedicaoDeRetomada
from graphow.context.token_counter import ContadorTokens

LIMITES_DECLARADOS: tuple[str, ...] = (
    "O braco 'sem grafo' e o despejo do subgrafo da sessao, nao a saida de outro produto.",
    "Taxa de patch rejeitado por rodada exige um agente real e nao esta medida aqui.",
    "A contagem de tokens usa o estimador calibrado do proprio Graphow, nao um tokenizador oficial.",
    "A condensacao do braco de retomada e texto gravado; a taxa de acerto de uma condensacao "
    "escrita por agente exige um agente real e fica fora da medicao.",
)


@dataclass(frozen=True)
class RelatorioDeAvaliacao:
    """Consolidação das medições, com as médias de tokens por tarefa bem-sucedida."""

    medicoes: tuple[MedicaoDaTarefa, ...]
    calibracao: str
    limites: tuple[str, ...] = LIMITES_DECLARADOS
    retomada: MedicaoDeRetomada | None = None
    entre_projetos: RelatorioEntreProjetos | None = None

    @classmethod
    def a_partir_de(
        cls,
        medicoes: Sequence[MedicaoDaTarefa],
        *,
        retomada: MedicaoDeRetomada | None = None,
        entre_projetos: RelatorioEntreProjetos | None = None,
    ) -> "RelatorioDeAvaliacao":
        """Monta o relatório registrando com que régua os tokens foram medidos."""
        return cls(
            medicoes=tuple(medicoes),
            calibracao=ContadorTokens.calibracao_em_uso(),
            retomada=retomada,
            entre_projetos=entre_projetos,
        )

    @property
    def bem_sucedidas(self) -> tuple[MedicaoDaTarefa, ...]:
        """Somente as tarefas concluídas entram na métrica número um."""
        return tuple(medicao for medicao in self.medicoes if medicao.concluida)

    @property
    def tokens_por_tarefa_bem_sucedida(self) -> float:
        """Média de tokens de contexto por tarefa concluída, com o grafo."""
        return self._media(tuple(m.tokens_com_grafo for m in self.bem_sucedidas))

    @property
    def tokens_por_tarefa_sem_grafo(self) -> float:
        """Mesma média no braço sem divulgação progressiva."""
        return self._media(tuple(m.tokens_sem_grafo for m in self.bem_sucedidas))

    @property
    def intervencoes_por_tarefa(self) -> float:
        """Média de respostas humanas exigidas por tarefa concluída."""
        return self._media(tuple(m.intervencoes_humanas for m in self.bem_sucedidas))

    @property
    def reducao_media(self) -> float:
        """Fração média de contexto poupada nas tarefas concluídas."""
        return self._media(tuple(m.reducao for m in self.bem_sucedidas))

    def _media(self, valores: Sequence[float]) -> float:
        """Média simples, com zero para o conjunto vazio."""
        return sum(valores) / len(valores) if valores else 0.0

    def formatar(self) -> tuple[str, ...]:
        """Linhas legíveis do relatório, prontas para o console."""
        return (
            self._cabecalho()
            + self._linhas_de_tarefas()
            + self._linhas_de_retomada()
            + self._linhas_entre_projetos()
            + self._rodape()
        )

    def _linhas_entre_projetos(self) -> tuple[str, ...]:
        """O braço entre projetos, quando foi medido."""
        if self.entre_projetos is None:
            return ()
        return self.entre_projetos.formatar()

    def _linhas_de_retomada(self) -> tuple[str, ...]:
        """O braço de retomada: a vista da sessão encerrada contra a leitura nó a nó."""
        if self.retomada is None:
            return ()
        medicao = self.retomada
        cobertura = "completa" if medicao.cobertura_completa else "incompleta"
        return (
            "",
            "=== RETOMADA DE SESSAO ENCERRADA ===",
            f"Sessao: {medicao.id_sessao}",
            f"Pela vista (fechamento + condensacao): {medicao.tokens_pela_vista} tokens",
            f"No a no ({medicao.nos_lidos_um_a_um} Decision/Evidence por expandir_no): {medicao.tokens_no_a_no} tokens",
            f"Reducao: {medicao.reducao * 100:.1f}% | decisoes vigentes entregues: "
            f"{medicao.decisoes_entregues}/{medicao.decisoes_vigentes} | cobertura {cobertura}",
        )

    def _cabecalho(self) -> tuple[str, ...]:
        """Resumo das médias de tokens por tarefa bem-sucedida."""
        return (
            "=== AVALIACAO: TOKENS POR TAREFA BEM-SUCEDIDA ===",
            f"Tarefas gravadas: {len(self.medicoes)} | concluidas: {len(self.bem_sucedidas)}",
            f"Calibracao do contador: {self.calibracao}",
            f"Com grafo:  {self.tokens_por_tarefa_bem_sucedida:.1f} tokens/tarefa",
            f"Sem grafo:  {self.tokens_por_tarefa_sem_grafo:.1f} tokens/tarefa",
            f"Reducao media de contexto: {self.reducao_media * 100:.1f}%",
            f"Intervencoes humanas por tarefa: {self.intervencoes_por_tarefa:.2f}",
            "",
            "Por tarefa:",
        )

    def _linhas_de_tarefas(self) -> tuple[str, ...]:
        """Uma linha por tarefa, com os dois custos lado a lado."""
        return tuple(
            f"  [{medicao.id_tarefa}] com={medicao.tokens_com_grafo} "
            f"sem={medicao.tokens_sem_grafo} "
            f"reducao={medicao.reducao * 100:.0f}% "
            f"intervencoes={medicao.intervencoes_humanas} "
            f"{'concluida' if medicao.concluida else 'pendente'}"
            for medicao in self.medicoes
        )

    def _rodape(self) -> tuple[str, ...]:
        """Os limites viajam junto do número, sempre."""
        return ("", "Limites desta medicao:") + tuple(f"  - {limite}" for limite in self.limites)
