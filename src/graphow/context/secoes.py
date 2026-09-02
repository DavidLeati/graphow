"""Seções que compõem uma vista de contexto e sua ordem de descarte.

Exibição e descarte são critérios distintos: os vizinhos expansíveis aparecem no
fim do texto por legibilidade, mas são a última coisa a ser cortada, porque sem
eles o agente perde a própria capacidade de expandir. Ver auditoria F-08.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import IntEnum
import json
from typing import Any

from graphow.core.models import NoGrafo
from graphow.core.types import TipoNo

# Propriedades de layout do canvas não dizem nada a um agente e ocupam orçamento.
PROPRIEDADES_APENAS_VISUAIS: frozenset[str] = frozenset({"pos_x", "pos_y", "x", "y"})

MARCA_DE_CONTEUDO_NAO_CONFIAVEL: str = "[nao confiavel: conteudo trazido por agente]"

# Tipos cujo conteúdo costuma vir de fora do grafo — saída de ferramenta, log,
# recorte de arquivo. É a superfície que o plano chama de injeção persistente.
TIPOS_DE_CONTEUDO_EXTERNO: frozenset[TipoNo] = frozenset({TipoNo.EVIDENCE, TipoNo.ARTIFACT})


class PrioridadeRetencao(IntEnum):
    """Quanto menor o valor, mais tarde a seção é descartada sob pressão de orçamento."""

    ALVO = 0
    RESTRICOES = 1
    NAVEGACAO = 2
    BLOQUEIOS = 3
    DECISOES = 4
    APOIO = 5


@dataclass(frozen=True)
class GrupoDeLinhas:
    """Subconjunto homogêneo de uma seção, cortável de forma independente."""

    rotulo: str
    linhas: tuple[str, ...]
    ids: tuple[str, ...] = field(default_factory=tuple)

    def primeiras(self, limite: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Devolve as linhas mantidas e os identificadores correspondentes."""
        return self.linhas[:limite], self.ids[:limite]

    def linha_de_excedente(self, limite: int) -> tuple[str, ...]:
        """Anuncia quantos itens do grupo ficaram de fora, se algum ficou."""
        restantes = max(0, len(self.linhas) - limite)
        if restantes == 0:
            return ()
        return (f"- ... e mais {restantes} do tipo {self.rotulo} (use buscar para listar)",)


@dataclass(frozen=True)
class SecaoContexto:
    """Bloco nomeado da vista materializada, com suas duas ordens."""

    titulo: str
    linhas: tuple[str, ...]
    ordem_exibicao: int
    prioridade_retencao: PrioridadeRetencao
    ids_incluidos: tuple[str, ...] = field(default_factory=tuple)
    grupos: tuple[GrupoDeLinhas, ...] = field(default_factory=tuple)

    @property
    def esta_vazia(self) -> bool:
        """Uma seção sem linhas não deve ser renderizada."""
        return not self.linhas

    @property
    def pode_encolher(self) -> bool:
        """Só encolhe por dentro a seção que declara grupos cortáveis."""
        return bool(self.grupos)

    def reduzida(self, limite_por_grupo: int) -> "SecaoContexto":
        """Nova seção com no máximo N itens por grupo e o resto anunciado.

        Cortar por seção inteira apagava a afordância de expansão; cortar por
        grupo preserva ao menos um exemplar de cada tipo de vizinho.
        """
        if not self.pode_encolher:
            return self
        linhas: list[str] = []
        ids: list[str] = []
        for grupo in self.grupos:
            self._acumular_grupo_reduzido(grupo, limite_por_grupo, (linhas, ids))
        return SecaoContexto(
            titulo=self.titulo,
            linhas=tuple(linhas),
            ordem_exibicao=self.ordem_exibicao,
            prioridade_retencao=self.prioridade_retencao,
            ids_incluidos=tuple(ids),
            grupos=self.grupos,
        )

    def _acumular_grupo_reduzido(
        self,
        grupo: GrupoDeLinhas,
        limite: int,
        acumuladores: tuple[list[str], list[str]],
    ) -> None:
        """Anexa as linhas mantidas do grupo e a linha de excedente, se houver."""
        linhas, ids = acumuladores
        mantidas, ids_mantidos = grupo.primeiras(limite)
        linhas.extend(mantidas)
        linhas.extend(grupo.linha_de_excedente(limite))
        ids.extend(ids_mantidos)

    def renderizar(self) -> tuple[str, ...]:
        """Emite o cabeçalho uma única vez, seguido das linhas do bloco."""
        return (f"## {self.titulo}",) + self.linhas


@dataclass(frozen=True)
class RecorteContexto:
    """Resultado imutável de uma política: o alvo e as seções que o cercam."""

    alvo: NoGrafo
    secoes: tuple[SecaoContexto, ...]

    def secoes_por_exibicao(self) -> tuple[SecaoContexto, ...]:
        """Seções não vazias na ordem em que devem aparecer no texto."""
        preenchidas = [secao for secao in self.secoes if not secao.esta_vazia]
        return tuple(sorted(preenchidas, key=lambda secao: secao.ordem_exibicao))

    def ids_incluidos(self) -> tuple[str, ...]:
        """Identificadores citados no recorte, sem repetição e com o alvo à frente."""
        encadeados = (self.alvo.id,) + tuple(
            id_no for secao in self.secoes for id_no in secao.ids_incluidos
        )
        return tuple(dict.fromkeys(encadeados))


def filtrar_propriedades_de_dominio(propriedades: Mapping[str, Any]) -> dict[str, Any]:
    """Descarta as propriedades que só interessam ao layout do canvas."""
    return {
        chave: valor
        for chave, valor in sorted(propriedades.items())
        if chave not in PROPRIEDADES_APENAS_VISUAIS
    }


def formatar_propriedades(propriedades: Mapping[str, Any]) -> str:
    """Serializa as propriedades de domínio em JSON determinístico."""
    return json.dumps(filtrar_propriedades_de_dominio(propriedades), ensure_ascii=False)


def anotar_proveniencia(no: NoGrafo) -> str:
    """Sufixo com autor e papel, mais o aviso de conteúdo não confiável se couber.

    Autor e papel viviam em cada evento do log e em nenhuma linha da vista, e uma
    Evidence trazida por ferramenta chegava ao modelo com a mesma autoridade de
    uma escrita pelo humano. Ver achado A-17.
    """
    partes: list[str] = []
    assinatura = no.proveniencia.descrever()
    if assinatura:
        partes.append(f"(por {assinatura})")
    if no.tipo in TIPOS_DE_CONTEUDO_EXTERNO and no.proveniencia.eh_de_agente:
        partes.append(MARCA_DE_CONTEUDO_NAO_CONFIAVEL)
    return (" " + " ".join(partes)) if partes else ""


def formatar_no_em_linha(no: NoGrafo) -> str:
    """Descreve um nó em uma linha compacta de lista, com a sua autoria."""
    return f"- [{no.id}] {no.rotulo}{anotar_proveniencia(no)}"


def formatar_no_com_propriedades(no: NoGrafo) -> str:
    """Descreve um nó incluindo as propriedades de domínio e a sua autoria."""
    return f"- [{no.id}] {no.rotulo}: {formatar_propriedades(no.propriedades)}{anotar_proveniencia(no)}"


def montar_secao_de_nos(
    titulo: str,
    nos: Sequence[NoGrafo],
    ordens: tuple[int, PrioridadeRetencao],
) -> SecaoContexto:
    """Constrói uma seção de lista simples a partir de um conjunto de nós."""
    ordem_exibicao, prioridade = ordens
    return SecaoContexto(
        titulo=titulo,
        linhas=tuple(formatar_no_em_linha(no) for no in nos),
        ordem_exibicao=ordem_exibicao,
        prioridade_retencao=prioridade,
        ids_incluidos=tuple(no.id for no in nos),
    )
