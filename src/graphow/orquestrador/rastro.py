"""O rastro de cada critério do Goal: o que o prova, o que o cobre, quem o atestou e o que o fere.

Uma leitura só, que o `--rastro` da CLI e a rota `/api/rastro` do canvas
usam. Para cada critério do plano:

- os testes de aceite (ou a checagem, ou a justificativa de já atendido) que o
  Criterio guarda, com o commit do aceite (muda quando o teste é refeito);
- as fatias que o cobrem (a lista `criterios` da Task, as de correção
  inclusive), com o commit de cada uma;
- a verificação mais recente que o julgou, com o veredito, o commit e a
  conferência dela na ponta da branch do Goal
  (orquestrador/conferencia_na_leitura.py, a mesma leitura da vista e do
  canvas);
- os Achados do orquestrador que o ferem (`fere`), com o estado.

O critério retirado pelo humano sai como retirado, com o motivo e a Decision
que o retirou, e mantém o rastro: o que se fez por ele não some.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from graphow.core import aceite as a
from graphow.core.models import NoGrafo
from graphow.core.orquestracao import ler_textos
from graphow.core.types import TipoAresta, TipoNo
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.conferencia_da_evidencia import ConferenciaDaEvidencia
from graphow.orquestrador.conferencia_na_leitura import LeituraPorGoal, conferencia_em_json, rotulo_da_conferencia
from graphow.orquestrador.leitura_das_verificacoes import VerificacaoRegistrada, do_orquestrador, retirado_pelo_humano
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.projection.graph_view import GrafoView


@dataclass(frozen=True)
class FatiaDoCriterio:
    """Uma fatia que cobre o critério: o código, o título, a situação, o commit e a verificação que ela corrige."""

    codigo: str
    titulo: str
    status: str
    commit: str
    corrige: str = ""


@dataclass(frozen=True)
class AtestadoDoCriterio:
    """A verificação mais recente que julgou o critério: o veredito, o commit e se ela vale na ponta."""

    verificacao: str
    tipo: str
    marco: str
    veredito: str
    commit: str
    conferencia: ConferenciaDaEvidencia | None = None

    def em_json(self) -> dict[str, Any]:
        """O atestado com a conferência como o canvas a manda (com o rótulo)."""
        return {**asdict(self), "conferencia": conferencia_em_json(self.conferencia)}


@dataclass(frozen=True)
class AchadoDoCriterio:
    """Um Achado que fere o critério: o título, a gravidade, o estado e a verificação (ou revisão) de onde veio."""

    id: str
    titulo: str
    gravidade: str
    estado: str
    origem: str


@dataclass(frozen=True)
class RastroDoCriterio:
    """O rastro de um critério: os quatro blocos e, quando o humano o retirou, a retirada."""

    codigo: str
    no: str
    texto: str
    testes: tuple[Mapping[str, Any], ...]
    checagem: tuple[str, ...]
    ja_atendido: str
    commit_do_aceite: str
    fatias: tuple[FatiaDoCriterio, ...]
    atestado: AtestadoDoCriterio | None
    achados: tuple[AchadoDoCriterio, ...]
    retirada: Mapping[str, Any] | None = None

    def em_json(self) -> dict[str, Any]:
        """O critério como a rota da API o devolve."""
        return {
            "codigo": self.codigo, "no": self.no, "texto": self.texto, "testes": [dict(t) for t in self.testes],
            "checagem": list(self.checagem), "ja_atendido": self.ja_atendido, "commit_do_aceite": self.commit_do_aceite,
            "fatias": [asdict(f) for f in self.fatias], "atestado": self.atestado.em_json() if self.atestado else None,
            "achados": [asdict(x) for x in self.achados], "retirada": dict(self.retirada) if self.retirada else None,
        }


@dataclass(frozen=True)
class RastroDoGoal:
    """O rastro de todos os critérios do plano do Goal, na ordem do plano."""

    id_goal: str
    rotulo: str
    fechado: bool
    criterios: tuple[RastroDoCriterio, ...] = ()

    def em_json(self) -> dict[str, Any]:
        """O rastro como a rota da API o devolve."""
        return {"goal": self.id_goal, "rotulo": self.rotulo, "fechado": self.fechado,
                "criterios": [criterio.em_json() for criterio in self.criterios]}


def ler_rastro(view: GrafoView, estado: EstadoDoGoal, leitura: LeituraPorGoal) -> RastroDoGoal:
    """O rastro do Goal lido (`ler_estado`), um critério do plano por vez; sem plano, sem critério."""
    leitor = _LeitorDoRastro(view, estado, leitura)
    itens = [c for c in (estado.plano or {}).get(a.CAMPO_CRITERIOS_DO_PLANO, []) if isinstance(c, Mapping)]
    return RastroDoGoal(estado.id_goal, estado.rotulo, estado.fechado, tuple(leitor.criterio(item) for item in itens))


class _LeitorDoRastro:
    """O que a leitura de cada critério consulta: o grafo, o estado do Goal e a conferência."""

    def __init__(self, view: GrafoView, estado: EstadoDoGoal, leitura: LeituraPorGoal) -> None:
        self._view: GrafoView = view
        self._estado: EstadoDoGoal = estado
        self._leitura: LeituraPorGoal = leitura

    def criterio(self, item: Mapping[str, Any]) -> RastroDoCriterio:
        """O rastro do critério do plano, lido do Criterio dele, das fatias, das verificações e dos Achados."""
        codigo, id_no = str(item.get("id") or ""), str(item.get("no") or "")
        no = self._view.obter_no(id_no) if id_no else None
        propriedades: Mapping[str, Any] = no.propriedades if no is not None else {}
        testes = propriedades.get(a.CAMPO_TESTES_DE_ACEITE)
        return RastroDoCriterio(
            codigo=codigo, no=id_no, texto=str(item.get("texto") or ""),
            testes=tuple(dict(t) for t in testes if isinstance(t, Mapping)) if isinstance(testes, list) else (),
            checagem=ler_textos(propriedades.get(a.CAMPO_CHECAGEM)),
            ja_atendido=str(propriedades.get(a.CAMPO_JA_ATENDIDO) or ""),
            commit_do_aceite=str(propriedades.get(a.CAMPO_COMMIT_DO_ACEITE) or ""),
            fatias=self._fatias(codigo), atestado=self._atestado(codigo, id_no), achados=self._achados(id_no),
            retirada=self._retirada(no),
        )

    def _fatias(self, codigo: str) -> tuple[FatiaDoCriterio, ...]:
        """As fatias cuja lista de critérios traz o código, na ordem do plano."""
        return tuple(FatiaDoCriterio(f.codigo, f.titulo, f.status, f.texto(m.CAMPO_COMMIT), f.texto(m.CAMPO_CORRIGE))
                     for f in self._estado.fatias if codigo in f.lista(m.CAMPO_CRITERIOS))

    def _atestado(self, codigo: str, id_no: str) -> AtestadoDoCriterio | None:
        """A verificação mais recente com parecer sobre o critério, conferida na ponta da branch do Goal."""
        julgaram = [(v, p) for v in self._estado.verificacoes for p in _pareceres(v) if _do_criterio(p, codigo, id_no)]
        if not julgaram:
            return None
        verificacao, parecer = julgaram[-1]
        no = self._view.obter_no(verificacao.id)
        conferencia = self._leitura.conferir(no) if no is not None else None
        return AtestadoDoCriterio(verificacao.id, verificacao.tipo, verificacao.marco, str(parecer.get("veredito") or ""),
                                  verificacao.commit, conferencia)

    def _achados(self, id_no: str) -> tuple[AchadoDoCriterio, ...]:
        """Os Achados do orquestrador que ferem o Criterio, na ordem em que nasceram."""
        origens = (self._view.obter_no(aresta.origem_id) for aresta in self._view.obter_arestas_entrada(id_no, TipoAresta.FERE))
        nos = sorted((n for n in origens if do_orquestrador(n) and n.tipo == TipoNo.ACHADO), key=lambda n: (n.ordem.seq_criacao, n.id))
        return tuple(AchadoDoCriterio(n.id, str(n.obter_propriedade("titulo") or n.rotulo), str(n.obter_propriedade(a.CAMPO_GRAVIDADE) or ""),
                                      str(n.obter_propriedade(a.CAMPO_ESTADO) or ""), _origem_do_achado(self._view, n)) for n in nos)

    def _retirada(self, no: NoGrafo | None) -> Mapping[str, Any] | None:
        """A retirada pelo humano que o kernel conta (a Decision dele, deste Goal), quando há."""
        if no is None or not retirado_pelo_humano(self._view, no, self._estado.id_goal):
            return None
        retirada = no.obter_propriedade(a.CAMPO_RETIRADO)
        return dict(retirada) if isinstance(retirada, Mapping) else None


def _pareceres(verificacao: VerificacaoRegistrada) -> list[Mapping[str, Any]]:
    """Os pareceres gravados na verificação."""
    pareceres = verificacao.propriedades.get(m.CAMPO_PARECERES)
    return [p for p in pareceres if isinstance(p, Mapping)] if isinstance(pareceres, list) else []


def _do_criterio(parecer: Mapping[str, Any], codigo: str, id_no: str) -> bool:
    """O parecer julga o critério: pelo nó, quando o parecer o traz; pelo código, no de antes do nó."""
    no = str(parecer.get(a.CAMPO_NO_DO_PARECER) or "")
    return no == id_no if no else str(parecer.get("id") or "") == codigo


def _origem_do_achado(view: GrafoView, achado: NoGrafo) -> str:
    """A Evidence de onde o Achado deriva: a verificação ou a revisão de risco."""
    return next((aresta.destino_id for aresta in view.obter_arestas_saida(achado.id, TipoAresta.DERIVA_DE)), "")


def formatar_rastro(rastro: RastroDoGoal) -> list[str]:
    """As linhas do `--rastro`: por critério, os testes, as fatias, a verificação e os achados."""
    linhas = [f"Rastro do Goal {rastro.id_goal}: {rastro.rotulo} [{'fechado' if rastro.fechado else 'aberto'}]"]
    if not rastro.criterios:
        return [*linhas, "Sem criterios: o Goal ainda nao foi planejado"]
    for criterio in rastro.criterios:
        linhas.append(f"{criterio.codigo}: {criterio.texto}" + (f" [{_texto_da_retirada(criterio.retirada)}]" if criterio.retirada else ""))
        linhas.extend(_linhas_dos_testes(criterio))
        linhas.append("  Fatias: " + (", ".join(_texto_da_fatia(f) for f in criterio.fatias) or "nenhuma"))
        linhas.append("  Verificacao: " + (_texto_do_atestado(criterio.atestado) if criterio.atestado else "nenhuma o julgou"))
        linhas.append("  Achados: " + ("; ".join(f"{x.id} {x.titulo} ({x.gravidade}, {x.estado})" for x in criterio.achados) or "nenhum"))
    return linhas


def _linhas_dos_testes(criterio: RastroDoCriterio) -> list[str]:
    """Os testes que provam o critério, com o commit do aceite; a checagem e o já atendido, quando é o caso."""
    aceite = f" (aceite em {criterio.commit_do_aceite[:12]})" if criterio.commit_do_aceite else ""
    provas = [f"{t.get('arquivo', '')}::{t.get('nome', '')} `{t.get('comando', '')}`" for t in criterio.testes]
    provas += [f"checagem: {item}" for item in criterio.checagem]
    provas += [f"ja atendido: {criterio.ja_atendido}"] if criterio.ja_atendido else []
    if len(provas) <= 1:
        return [f"  Testes{aceite}: " + (provas[0] if provas else "nenhum ainda")]
    return [f"  Testes{aceite}:", *(f"    - {prova}" for prova in provas)]


def _texto_da_fatia(fatia: FatiaDoCriterio) -> str:
    """`F1 em <commit> (concluido)`, com a verificação que a fatia de correção corrige."""
    corrige = f", corrige {fatia.corrige}" if fatia.corrige else ""
    return f"{fatia.codigo} em {fatia.commit[:12] or '-'} ({fatia.status}{corrige})"


def _texto_do_atestado(atestado: AtestadoDoCriterio) -> str:
    """`ver-x-2 (conferencia, M1): atende em <commit> [vigente]`."""
    marca = f" [{rotulo_da_conferencia(atestado.conferencia)}]" if atestado.conferencia else ""
    return f"{atestado.verificacao} ({atestado.tipo or '-'}, {atestado.marco or '-'}): {atestado.veredito} em {atestado.commit[:12]}{marca}"


def _texto_da_retirada(retirada: Mapping[str, Any]) -> str:
    """`retirado pelo humano (decisao, por quem): motivo`."""
    por = f", por {retirada['por']}" if retirada.get("por") else ""
    return f"retirado pelo humano ({retirada.get('decisao', '')}{por}): {retirada.get('motivo', '')}"
