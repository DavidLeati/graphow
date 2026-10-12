"""A saída de cada papel como objeto tipado, com a conferência que o schema não faz.

O schema garante a forma; aqui se garante o sentido: ids únicos, fatia que
cobre critério que existe, dependência que aponta fatia do plano e não fecha
ciclo, todo critério coberto, os critérios e as decisões que o humano já fixou
mantidos, os marcos que repartem as fatias em ordem e a dúvida com pergunta.

Um marco é um conjunto de fatias que, juntas, entregam critérios
verificáveis: ao fim de cada um, uma sessão nova do verificador julga os
critérios que ele completou (os que a última fatia que os cobre está nele), e
o último marco é a verificação final, sobre o Goal inteiro. Toda fatia está
em exatamente um marco, nenhuma depende de fatia de um marco seguinte, e o
marco que não é o último completa ao menos um critério. O plano sem marcos (o
de antes da fase 2) é um marco só, o final. A saída do verificador mora em
orquestrador/saida_do_verificador.py. Saída que não confere volta à mesma
sessão com a lista de problemas, uma vez (orquestrador/sessoes_de_papel.py).
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

STATUS_DUVIDA: str = "duvida"
MARCO_UNICO: str = "M1"


def _textos(valor: object) -> tuple[str, ...]:
    """A lista de textos do JSON, sem vazios."""
    return tuple(str(item).strip() for item in valor if str(item).strip()) if isinstance(valor, list) else ()


@dataclass(frozen=True)
class Criterio:
    """Um critério de aceite: id (C1...), texto completo e como se prova."""

    id: str
    texto: str
    verificacao: str


@dataclass(frozen=True)
class Decisao:
    """Uma decisão que o trabalho segue, com o motivo."""

    id: str
    texto: str
    motivo: str


@dataclass(frozen=True)
class Fatia:
    """Uma fatia vertical do plano: o que entrega, que critérios cobre, onde mexe e de que depende."""

    id: str
    titulo: str
    objetivo: str
    criterios: tuple[str, ...] = ()
    arquivos: tuple[str, ...] = ()
    depende_de: tuple[str, ...] = ()
    modelo: str = ""

    @classmethod
    def de_json(cls, dados: Mapping[str, Any]) -> "Fatia":
        """A fatia como o planejador a devolveu."""
        return cls(
            id=str(dados["id"]).strip(),
            titulo=str(dados["titulo"]).strip(),
            objetivo=str(dados["objetivo"]).strip(),
            criterios=_textos(dados.get("criterios")),
            arquivos=_textos(dados.get("arquivos")),
            depende_de=_textos(dados.get("depende_de")),
            modelo=str(dados.get("modelo", "")),
        )


@dataclass(frozen=True)
class Marco:
    """Um marco do plano: as fatias que, juntas, entregam critérios verificáveis."""

    id: str
    titulo: str
    fatias: tuple[str, ...]


@dataclass(frozen=True)
class Plano:
    """O plano do Goal: título, comando da suíte, critérios, decisões, fatias e os marcos que as repartem."""

    titulo: str
    comando_suite: str
    criterios: tuple[Criterio, ...]
    decisoes: tuple[Decisao, ...]
    fatias: tuple[Fatia, ...]
    fora_do_escopo: tuple[str, ...] = ()
    marcos: tuple[Marco, ...] = ()

    @classmethod
    def de_json(cls, dados: Mapping[str, Any]) -> "Plano":
        """O plano como o planejador o devolveu, já conferido pelo schema."""
        return cls(
            titulo=str(dados["titulo"]).strip(),
            comando_suite=str(dados["comando_suite"]).strip(),
            criterios=tuple(Criterio(str(c["id"]).strip(), str(c["texto"]).strip(), str(c["verificacao"])) for c in dados["criterios"]),
            decisoes=tuple(Decisao(str(d["id"]).strip(), str(d["texto"]).strip(), str(d["motivo"]).strip()) for d in dados["decisoes"]),
            fatias=tuple(Fatia.de_json(fatia) for fatia in dados["fatias"]),
            fora_do_escopo=_textos(dados.get("fora_do_escopo")),
            marcos=_marcos(dados),
        )

    def marco_da_fatia(self, id_fatia: str) -> str:
        """O marco em que a fatia está; vazio quando nenhum a traz."""
        return next((marco.id for marco in self.marcos if id_fatia in marco.fatias), "")

    def criterios_do_marco(self, id_marco: str) -> tuple[str, ...]:
        """Os critérios que o marco completa (a última fatia que os cobre está nele); no último, todos."""
        ordem = [marco.id for marco in self.marcos]
        if ordem and id_marco == ordem[-1]:
            return tuple(criterio.id for criterio in self.criterios)
        return tuple(criterio.id for criterio in self.criterios if self._ultimo_marco(criterio.id, ordem) == id_marco)

    def _ultimo_marco(self, id_criterio: str, ordem: Sequence[str]) -> str:
        """O marco mais adiante em que há fatia que cobre o critério."""
        marcos = [self.marco_da_fatia(fatia.id) for fatia in self.fatias if id_criterio in fatia.criterios]
        posicoes = [ordem.index(marco) for marco in marcos if marco in ordem]
        return ordem[max(posicoes)] if posicoes else ""

    def com_criterios_do_humano(self, criterios: Sequence[Criterio]) -> "Plano":
        """O plano com o texto e o tipo de verificação dos critérios que o humano fixou, como ele os escreveu."""
        do_humano = {criterio.id: criterio for criterio in criterios}
        return replace(self, criterios=tuple(do_humano.get(criterio.id, criterio) for criterio in self.criterios))


@dataclass(frozen=True)
class IdsFixados:
    """Os critérios e as decisões que o Goal já trazia (do gerente): o plano os mantém com o mesmo id."""

    criterios: tuple[str, ...] = ()
    decisoes: tuple[str, ...] = ()


def _marcos(dados: Mapping[str, Any]) -> tuple[Marco, ...]:
    """Os marcos do plano; o plano sem eles é um marco só, com todas as fatias."""
    marcos = dados.get("marcos")
    if isinstance(marcos, list) and marcos:
        return tuple(Marco(str(m["id"]).strip(), str(m.get("titulo", "")).strip(), _textos(m.get("fatias"))) for m in marcos)
    return (Marco(MARCO_UNICO, "O Goal inteiro", tuple(str(f["id"]).strip() for f in dados.get("fatias", []))),)


def conferir_plano(plano: Plano, fixados: IdsFixados) -> tuple[str, ...]:
    """Os problemas de sentido do plano; vazio quando ele pode ser gravado."""
    criterios = [criterio.id for criterio in plano.criterios]
    fatias = [fatia.id for fatia in plano.fatias]
    problemas = [
        *_repetidos("criterio", criterios),
        *_repetidos("decisao", [decisao.id for decisao in plano.decisoes]),
        *_repetidos("fatia", fatias),
        *(f"o criterio fixado {id_c} sumiu do plano" for id_c in fixados.criterios if id_c not in criterios),
        *(f"a decisao fixada {id_d} sumiu do plano" for id_d in fixados.decisoes if id_d not in {d.id for d in plano.decisoes}),
        *_problemas_das_fatias(plano.fatias, set(criterios)),
        *(f"o criterio {id_c} nao e coberto por nenhuma fatia" for id_c in criterios if not _coberto(id_c, plano.fatias)),
    ]
    return tuple(problemas) or _problemas_dos_marcos(plano) or _ciclo(plano.fatias)


def _problemas_dos_marcos(plano: Plano) -> tuple[str, ...]:
    """Toda fatia num marco só, dependência só para trás e marco intermediário que completa critério."""
    ids = [fatia.id for fatia in plano.fatias]
    citadas = [id_f for marco in plano.marcos for id_f in marco.fatias]
    ordem = {id_f: posicao for posicao, marco in enumerate(plano.marcos) for id_f in marco.fatias}
    return (
        *_repetidos("marco", [marco.id for marco in plano.marcos]),
        *(f"o marco {marco.id} cita {id_f}, que nao e fatia do plano" for marco in plano.marcos for id_f in marco.fatias if id_f not in ids),
        *(f"a fatia {id_f} nao esta em nenhum marco" for id_f in ids if id_f not in citadas),
        *(f"a fatia {id_f} esta em mais de um marco" for id_f in sorted({i for i in citadas if citadas.count(i) > 1})),
        *(
            f"a fatia {fatia.id} depende de {dependencia}, que e de um marco seguinte"
            for fatia in plano.fatias for dependencia in fatia.depende_de if ordem.get(dependencia, -1) > ordem.get(fatia.id, -1)
        ),
        *(
            f"o marco {marco.id} nao completa nenhum criterio: junte-o ao seguinte"
            for marco in plano.marcos[:-1] if not plano.criterios_do_marco(marco.id)
        ),
    )


def _repetidos(nome: str, ids: Sequence[str]) -> list[str]:
    """Os ids que aparecem mais de uma vez."""
    return [f"{nome} {id_repetido} repetido" for id_repetido in sorted({i for i in ids if ids.count(i) > 1})]


def _problemas_das_fatias(fatias: Sequence[Fatia], criterios: set[str]) -> list[str]:
    """Critério que não existe e dependência que não aponta fatia do plano, ou aponta a si mesma."""
    ids = {fatia.id for fatia in fatias}
    problemas: list[str] = []
    for fatia in fatias:
        problemas.extend(f"a fatia {fatia.id} cita o criterio {c}, que nao existe" for c in fatia.criterios if c not in criterios)
        problemas.extend(f"a fatia {fatia.id} depende de {d}, que nao e fatia do plano" for d in fatia.depende_de if d not in ids)
        problemas.extend(f"a fatia {fatia.id} depende de si mesma" for d in fatia.depende_de if d == fatia.id)
    return problemas


def _coberto(id_criterio: str, fatias: Iterable[Fatia]) -> bool:
    """Alguma fatia cobre o critério."""
    return any(id_criterio in fatia.criterios for fatia in fatias)


def _ciclo(fatias: Sequence[Fatia]) -> tuple[str, ...]:
    """As fatias que dependem umas das outras em ciclo, pela ordem topológica que não fecha."""
    pendentes = {fatia.id: set(fatia.depende_de) for fatia in fatias}
    while pendentes:
        prontas = {id_f for id_f, deps in pendentes.items() if not deps & set(pendentes)}
        if not prontas:
            return (f"as fatias {', '.join(sorted(pendentes))} dependem umas das outras em ciclo",)
        pendentes = {id_f: deps for id_f, deps in pendentes.items() if id_f not in prontas}
    return ()


@dataclass(frozen=True)
class SaidaDoExecutor:
    """O que o executor devolveu da fatia."""

    status: str
    resumo: str
    arquivos: tuple[str, ...] = ()
    testes: tuple[str, ...] = ()
    duvida: str = ""

    @classmethod
    def de_json(cls, dados: Mapping[str, Any]) -> "SaidaDoExecutor":
        """A saída como o executor a devolveu."""
        return cls(
            status=str(dados["status"]),
            resumo=str(dados["resumo"]).strip(),
            arquivos=_textos(dados.get("arquivos")),
            testes=_textos(dados.get("testes")),
            duvida=str(dados.get("duvida", "")).strip(),
        )

    def conferir(self) -> tuple[str, ...]:
        """A dúvida precisa da pergunta."""
        return ("status duvida sem a pergunta em 'duvida'",) if self.status == STATUS_DUVIDA and not self.duvida else ()
