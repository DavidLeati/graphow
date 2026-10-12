"""A saída de cada papel como objeto tipado, com a conferência que o schema não faz.

O schema garante a forma; aqui se garante o sentido: ids únicos, fatia que
cobre critério que existe, dependência que aponta fatia do plano e não fecha
ciclo, todo critério coberto, os critérios e as decisões que o humano já fixou
mantidos, a dúvida com pergunta e a verificação que dá parecer sobre cada
critério e lista os comandos que rodou. Saída que não confere volta à mesma
sessão com a lista de problemas, uma vez (orquestrador/sessoes_de_papel.py).
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

VEREDITO_QUE_ATENDE: str = "atende"
GRAVIDADE_BLOQUEANTE: str = "bloqueante"
GRAVIDADE_ACOMPANHAMENTO: str = "acompanhamento"
STATUS_DUVIDA: str = "duvida"
TITULO_DA_SUITE_VERMELHA: str = "A suite do plano falhou no commit verificado"


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


@dataclass(frozen=True)
class Parecer:
    """O veredito do verificador sobre um critério ou uma decisão, com a prova."""

    id: str
    veredito: str
    prova: str


@dataclass(frozen=True)
class Achado:
    """Um problema que o verificador achou, com a gravidade e o que ele fere."""

    gravidade: str
    titulo: str
    descricao: str
    local: str = ""
    criterios: tuple[str, ...] = ()

    def em_json(self) -> dict[str, Any]:
        """O achado para gravar na Evidence."""
        return {"gravidade": self.gravidade, "titulo": self.titulo, "descricao": self.descricao,
                "local": self.local, "criterios": list(self.criterios)}


@dataclass(frozen=True)
class ComandoRodado:
    """Um comando que o verificador rodou: o que, com que código saiu e um trecho do que imprimiu."""

    comando: str
    codigo: int
    saida: str

    def em_json(self) -> dict[str, Any]:
        """O comando para gravar na Evidence."""
        return {"comando": self.comando, "codigo": self.codigo, "saida": self.saida}


def _comandos(valor: object) -> tuple[ComandoRodado, ...]:
    """Os comandos rodados do JSON; a falta deles é problema da conferência, não da leitura."""
    itens = valor if isinstance(valor, list) else []
    return tuple(ComandoRodado(str(c["comando"]).strip(), int(c["codigo"]), str(c["saida"]).strip()) for c in itens)


@dataclass(frozen=True)
class Verificacao:
    """O que o verificador devolveu do Goal inteiro."""

    resumo: str
    criterios: tuple[Parecer, ...]
    decisoes: tuple[Parecer, ...] = ()
    achados: tuple[Achado, ...] = field(default_factory=tuple)
    comandos: tuple[ComandoRodado, ...] = ()

    @classmethod
    def de_json(cls, dados: Mapping[str, Any]) -> "Verificacao":
        """A verificação como o verificador a devolveu."""
        def parecer(item: Mapping[str, Any]) -> Parecer:
            return Parecer(str(item["id"]).strip(), str(item["veredito"]), str(item["prova"]).strip())

        return cls(
            resumo=str(dados["resumo"]).strip(),
            criterios=tuple(parecer(item) for item in dados["criterios"]),
            decisoes=tuple(parecer(item) for item in dados["decisoes"]),
            achados=tuple(
                Achado(str(a["gravidade"]), str(a["titulo"]).strip(), str(a["descricao"]).strip(),
                       str(a.get("local", "")).strip(), _textos(a.get("criterios")))
                for a in dados["achados"]
            ),
            comandos=_comandos(dados.get("comandos")),
        )

    def com_a_suite_vermelha(self, descricao: str) -> "Verificacao":
        """A verificação com o bloqueante da suíte que o orquestrador rodou no commit verificado e viu falhar."""
        return replace(self, achados=(*self.achados, Achado(GRAVIDADE_BLOQUEANTE, TITULO_DA_SUITE_VERMELHA, descricao)))

    def bloqueantes(self) -> tuple[Achado, ...]:
        """Os achados bloqueantes e, para o critério ou decisão sem `atende` que nenhum cita, um sintético."""
        declarados = tuple(achado for achado in self.achados if achado.gravidade == GRAVIDADE_BLOQUEANTE)
        citados = {id_c for achado in declarados for id_c in achado.criterios}
        sinteticos = tuple(
            Achado(GRAVIDADE_BLOQUEANTE, f"{parecer.id} {parecer.veredito}", parecer.prova, "", (parecer.id,))
            for parecer in (*self.criterios, *self.decisoes)
            if parecer.veredito != VEREDITO_QUE_ATENDE and parecer.id not in citados
        )
        return declarados + sinteticos

    def acompanhamentos(self) -> tuple[Achado, ...]:
        """Os achados que não ferem critério nem decisão."""
        return tuple(achado for achado in self.achados if achado.gravidade == GRAVIDADE_ACOMPANHAMENTO)


def conferir_verificacao(verificacao: Verificacao, criterios: Sequence[str], decisoes: Sequence[str]) -> tuple[str, ...]:
    """Um parecer por critério e por decisão do plano, achado que cita só o que existe e ao menos um comando rodado."""
    dados = [parecer.id for parecer in verificacao.criterios]
    dadas = [parecer.id for parecer in verificacao.decisoes]
    conhecidos = {*criterios, *decisoes}
    return (
        *(() if verificacao.comandos else ("a verificacao nao lista nenhum comando rodado em 'comandos'",)),
        *(f"falta o parecer do criterio {id_c}" for id_c in criterios if id_c not in dados),
        *(f"falta o parecer da decisao {id_d}" for id_d in decisoes if id_d not in dadas),
        *_repetidos("parecer", dados + dadas),
        *(
            f"o achado '{achado.titulo}' cita {id_c}, que nao e criterio nem decisao do plano"
            for achado in verificacao.achados for id_c in achado.criterios if id_c not in conhecidos
        ),
    )
