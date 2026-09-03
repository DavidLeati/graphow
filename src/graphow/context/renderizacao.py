"""Renderização em Markdown de um recorte de contexto sob orçamento de tokens.

Sob pressão de orçamento a vista desce a escada de `context/corte.py`, do texto
mais completo ao mais enxuto. A seção de vizinhos encolhe por dentro antes de
qualquer coisa sumir: sem ela o agente perde a própria capacidade de expandir.
O corte linha a linha pelo fim, que era o comportamento original, comia
justamente essa seção e recontava o texto inteiro a cada linha removida.
Ver auditoria F-08 e achado A-08.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from graphow.context.corte import PlanoDeCorte, montar_escada_de_corte
from graphow.context.secoes import RecorteContexto, SecaoContexto, anotar_ordem, formatar_propriedades
from graphow.context.tokenizacao import ESTIMADOR_PADRAO, EstimadorTokens
from graphow.core.exceptions import ErroOrcamentoExcedido

AVISO_DE_TRUNCAGEM: str = "[AVISO: secoes secundarias omitidas por limite de tokens]"


@dataclass(frozen=True)
class CandidatoRenderizado:
    """Texto já montado e medido, aguardando aprovação pelo orçamento."""

    conteudo: str
    tokens_estimados: int
    secoes: tuple[SecaoContexto, ...]


@dataclass(frozen=True)
class TextoRenderizado:
    """Resultado imutável da renderização, já enquadrado no orçamento."""

    conteudo: str
    tokens_estimados: int
    secoes_incluidas: tuple[str, ...]
    ids_incluidos: tuple[str, ...]
    ids_por_secao: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


class RenderizadorContexto:
    """Converte um recorte em Markdown, descendo a escada de corte até caber."""

    def __init__(self, estimador: EstimadorTokens | None = None) -> None:
        self._estimador: EstimadorTokens = estimador or ESTIMADOR_PADRAO

    def renderizar(self, recorte: RecorteContexto, orcamento_tokens: int) -> TextoRenderizado:
        """Monta o texto mais completo que couber no orçamento informado."""
        cabecalho = self._montar_cabecalho(recorte)
        secoes = recorte.secoes_por_exibicao()
        for plano in montar_escada_de_corte():
            candidato = self._montar_candidato(cabecalho, secoes, plano)
            if candidato.tokens_estimados <= orcamento_tokens:
                return self._montar_resultado(candidato, recorte)
        raise ErroOrcamentoExcedido(
            "Orcamento insuficiente para conter o no alvo e suas restricoes",
            {"orcamento": str(orcamento_tokens)},
        )

    def _montar_candidato(
        self,
        cabecalho: Sequence[str],
        secoes: Sequence[SecaoContexto],
        plano: PlanoDeCorte,
    ) -> CandidatoRenderizado:
        """Aplica um degrau da escada e mede o texto resultante."""
        mantidas = self._aplicar_plano(secoes, plano)
        conteudo = self._montar_texto(cabecalho, mantidas, truncado=plano.houve_corte)
        return CandidatoRenderizado(
            conteudo=conteudo,
            tokens_estimados=self._estimador.estimar_texto(conteudo),
            secoes=mantidas,
        )

    def _aplicar_plano(
        self,
        secoes: Sequence[SecaoContexto],
        plano: PlanoDeCorte,
    ) -> tuple[SecaoContexto, ...]:
        """Descarta as prioridades do degrau e encolhe o que ainda pode encolher."""
        sobreviventes = [
            secao for secao in secoes if secao.prioridade_retencao not in plano.prioridades_descartadas
        ]
        if plano.limite_de_vizinhos is None:
            return tuple(sobreviventes)
        reduzidas = [secao.reduzida(plano.limite_de_vizinhos) for secao in sobreviventes]
        return tuple(secao for secao in reduzidas if not secao.esta_vazia)

    def _montar_resultado(
        self,
        candidato: CandidatoRenderizado,
        recorte: RecorteContexto,
    ) -> TextoRenderizado:
        """Empacota o texto aceito junto do que ele de fato cita."""
        ids_das_secoes = tuple(id_no for secao in candidato.secoes for id_no in secao.ids_incluidos)
        return TextoRenderizado(
            conteudo=candidato.conteudo,
            tokens_estimados=candidato.tokens_estimados,
            secoes_incluidas=tuple(secao.titulo for secao in candidato.secoes),
            ids_incluidos=tuple(dict.fromkeys((recorte.alvo.id,) + ids_das_secoes)),
            ids_por_secao={secao.titulo: secao.ids_incluidos for secao in candidato.secoes},
        )

    def _montar_cabecalho(self, recorte: RecorteContexto) -> tuple[str, ...]:
        """Bloco de abertura com a identidade e as propriedades do nó alvo.

        A ordem entra como sufixo, e não como linha própria com a data por
        extenso: o cabeçalho é obrigatório em toda vista, então tudo que se
        acrescenta aqui sai do orçamento de todo agente. O inteiro responde a
        ordem por poucos tokens; a data por extenso fica em `expandir_no`, que é
        justamente o detalhe sob demanda.
        """
        alvo = recorte.alvo
        return (
            f"# [VISTA DE CONTEXTO] No Alvo: {alvo.rotulo} ({alvo.id}){anotar_ordem(alvo)}",
            f"- Tipo: {alvo.tipo.value}",
            f"- Propriedades: {formatar_propriedades(alvo.propriedades)}",
        )

    def _montar_texto(
        self,
        cabecalho: Sequence[str],
        secoes: Sequence[SecaoContexto],
        truncado: bool,
    ) -> str:
        """Concatena cabeçalho e seções, avisando quando algo foi omitido."""
        linhas: list[str] = list(cabecalho)
        for secao in secoes:
            linhas.append("")
            linhas.extend(secao.renderizar())
        if truncado:
            linhas.extend(("", AVISO_DE_TRUNCAGEM))
        return "\n".join(linhas)
