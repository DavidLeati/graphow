"""A saída de cada papel como objeto tipado, com a conferência que o schema não faz.

O schema garante a forma; aqui se garante o sentido: ids únicos, fatia que
cobre critério que existe, dependência que aponta fatia do plano e não fecha
ciclo, todo critério coberto, os critérios e as decisões que o humano já fixou
mantidos e a dúvida com pergunta. A saída do verificador mora em
orquestrador/saida_do_verificador.py. Saída que não confere volta à mesma
sessão com a lista de problemas, uma vez (orquestrador/sessoes_de_papel.py).
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

STATUS_DUVIDA: str = "duvida"


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
class Plano:
    """O plano do Goal: título, comando da suíte, critérios, decisões e fatias."""

    titulo: str
    comando_suite: str
    criterios: tuple[Criterio, ...]
    decisoes: tuple[Decisao, ...]
    fatias: tuple[Fatia, ...]
    fora_do_escopo: tuple[str, ...] = ()

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
        )

    def com_criterios_do_humano(self, criterios: Sequence[Criterio]) -> "Plano":
        """O plano com o texto e o tipo de verificação dos critérios que o humano fixou, como ele os escreveu."""
        do_humano = {criterio.id: criterio for criterio in criterios}
        return replace(self, criterios=tuple(do_humano.get(criterio.id, criterio) for criterio in self.criterios))


@dataclass(frozen=True)
class IdsFixados:
    """Os critérios e as decisões que o Goal já trazia (do gerente): o plano os mantém com o mesmo id."""

    criterios: tuple[str, ...] = ()
    decisoes: tuple[str, ...] = ()


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
    return tuple(problemas) or _ciclo(plano.fatias)


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
