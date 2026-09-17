"""Fechamento determinístico de uma subárvore: o que vigora, o que segue aberto, o último artefato.

O harness sabia escrever `resumo` ao encerrar a Sessao, e nenhuma sessão passou
por ali: no banco real, 0 de 13 tinham a propriedade. O esqueleto do fechamento
não pode depender de alguém lembrar de escrevê-lo. Ele é uma dobra do estado,
como o rollup, recalculada a cada commit: uma sessão reaberta atualiza sozinha,
e nada derivado entra no log.

O que a dobra responde é o que quem retoma uma sessão pergunta primeiro: quais
decisões ainda valem, quais dúvidas seguem sem resposta, que restrições a
escopam e qual foi o último artefato entregue. A prosa que explica o porquê é
trabalho de agente, e entra pelo PatchBoard como Note de condensação.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from graphow.core.models import GrafoEstado, NoGrafo
from graphow.core.types import StatusQuestion, TipoAresta, TipoNo

# Quantos identificadores uma linha de panorama nomeia antes de apenas contar.
# Acima disso a linha da sessão volta a ser a lista que o panorama substituiu.
LIMITE_DE_IDS_POR_LINHA: int = 5


@dataclass(frozen=True)
class FechamentoDeSubarvore:
    """Esqueleto determinístico do que uma subárvore deixou em vigor."""

    decisoes_vigentes: tuple[str, ...] = field(default_factory=tuple)
    decisoes_substituidas: int = 0
    questoes_abertas: tuple[str, ...] = field(default_factory=tuple)
    restricoes: tuple[str, ...] = field(default_factory=tuple)
    ultimo_artefato: str = ""
    seq_ultimo_artefato: int = 0

    @property
    def esta_vazio(self) -> bool:
        """Sem decisão, dúvida, restrição ou artefato não há fechamento a mostrar."""
        return not (
            self.decisoes_vigentes or self.questoes_abertas or self.restricoes or self.ultimo_artefato
        )

    def descrever(self, limite: int = LIMITE_DE_IDS_POR_LINHA) -> tuple[str, ...]:
        """Linhas compactas do fechamento, na casa de vinte tokens cada."""
        if self.esta_vazio:
            return ()
        partes = [
            f"vigora: {_nomear(self.decisoes_vigentes, limite)}",
            f"aberto: {len(self.questoes_abertas)} duvidas",
        ]
        if self.restricoes:
            partes.append(f"restricoes: {_nomear(self.restricoes, limite)}")
        linhas = [" | ".join(partes)]
        if self.ultimo_artefato:
            linhas.append(f"ultimo artefato: {self.ultimo_artefato} (log #{self.seq_ultimo_artefato})")
        return tuple(linhas)

    def em_dicionario(self) -> dict[str, object]:
        """Forma serializável para o canvas e para as respostas REST."""
        return {
            "decisoes_vigentes": list(self.decisoes_vigentes),
            "decisoes_substituidas": self.decisoes_substituidas,
            "questoes_abertas": list(self.questoes_abertas),
            "restricoes": list(self.restricoes),
            "ultimo_artefato": self.ultimo_artefato,
            "seq_ultimo_artefato": self.seq_ultimo_artefato,
        }


def _nomear(ids: Sequence[str], limite: int) -> str:
    """Lista os primeiros identificadores e conta o resto, ou diz que não há nenhum."""
    if not ids:
        return "nenhuma"
    excedente = len(ids) - limite
    cabeca = ", ".join(ids[:limite])
    return f"{cabeca} (+{excedente})" if excedente > 0 else cabeca


def decisoes_substituidas(estado: GrafoEstado) -> frozenset[str]:
    """Decisões que receberam uma aresta `substitui`: já não vigoram."""
    return frozenset(
        aresta.destino_id
        for aresta in estado.arestas.values()
        if aresta.tipo == TipoAresta.SUBSTITUI
    )


def calcular_fechamento(nos: Sequence[NoGrafo], substituidas: frozenset[str]) -> FechamentoDeSubarvore:
    """Dobra os nós alcançados no esqueleto do fechamento, em ordem estável."""
    decisoes = _ordenar(no for no in nos if no.tipo == TipoNo.DECISION)
    vigentes = tuple(no.id for no in decisoes if no.id not in substituidas)
    artefato = _ultimo_por_ordem(no for no in nos if no.tipo == TipoNo.ARTIFACT)
    return FechamentoDeSubarvore(
        decisoes_vigentes=vigentes,
        decisoes_substituidas=len(decisoes) - len(vigentes),
        questoes_abertas=tuple(no.id for no in _ordenar(no for no in nos if _eh_questao_aberta(no))),
        restricoes=tuple(no.id for no in _ordenar(no for no in nos if no.tipo == TipoNo.CONSTRAINT)),
        ultimo_artefato=artefato.id if artefato is not None else "",
        seq_ultimo_artefato=artefato.ordem.seq_criacao if artefato is not None else 0,
    )


def _ordenar(nos: Iterable[NoGrafo]) -> tuple[NoGrafo, ...]:
    """Ordem total: posição de nascimento no log e, em empate, o identificador."""
    return tuple(sorted(nos, key=lambda no: (no.ordem.seq_criacao, no.id)))


def _ultimo_por_ordem(nos: Iterable[NoGrafo]) -> NoGrafo | None:
    """O nó que nasceu por último; o identificador desempata quando não há sequência."""
    ordenados = _ordenar(nos)
    return ordenados[-1] if ordenados else None


def _eh_questao_aberta(no: NoGrafo) -> bool:
    """Uma Question sem resposta é o que a próxima sessão herda como pendência."""
    if no.tipo != TipoNo.QUESTION:
        return False
    return no.obter_propriedade("status", StatusQuestion.ABERTA.value) == StatusQuestion.ABERTA.value
