"""A saída do verificador como objeto tipado: os pareceres, os comandos e os achados, com a gravidade decidida pelo código.

No portão da fase 1 os verificadores acharam os defeitos que o auditor depois
chamou de bloqueantes (o título contado em unidades UTF-16 contra "até 200
caracteres", a quantidade negativa que aumentava o saldo, o CSV em ANSI com
traceback), mas os classificaram como acompanhamento, e o Goal fechou com eles.
Por isso o verificador não diz mais a gravidade: diz, por achado, os critérios
e as decisões que ele toca (a lista pode ser vazia) e a prova. O código decide:
o achado que toca critério ou decisão é bloqueante, sem exceção, inclusive o
defeito que "já existia antes"; só o que não toca nada é acompanhamento. O que
o próprio orquestrador viu falhar (a suíte, o teste de aceite) é bloqueante
por origem. A `severidade` que o verificador sugere fica gravada, informativa,
e não muda o destino.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from graphow.core import aceite as a

ORIGEM_DO_VERIFICADOR: str = "verificador"
ORIGEM_DO_ORQUESTRADOR: str = "orquestrador"
TITULO_DA_SUITE_VERMELHA: str = "A suite do plano falhou no commit verificado"
# Quanto do fim da saída vai como prova do achado que o orquestrador registra.
LIMITE_DA_PROVA: int = 2000


def _textos(valor: object) -> tuple[str, ...]:
    """A lista de textos do JSON, sem vazios."""
    return tuple(str(item).strip() for item in valor if str(item).strip()) if isinstance(valor, list) else ()


@dataclass(frozen=True)
class Parecer:
    """O veredito do verificador sobre um critério ou uma decisão, com a prova."""

    id: str
    veredito: str
    prova: str


@dataclass(frozen=True)
class Achado:
    """Um problema achado na verificação: o que é, a prova, onde, o que ele toca e de quem veio."""

    titulo: str
    descricao: str
    prova: str = ""
    local: str = ""
    criterios: tuple[str, ...] = ()
    decisoes: tuple[str, ...] = ()
    severidade: str = ""
    origem: str = ORIGEM_DO_VERIFICADOR

    @property
    def toca(self) -> tuple[str, ...]:
        """Os critérios e as decisões que o achado toca, sem repetir."""
        return tuple(dict.fromkeys((*self.criterios, *self.decisoes)))

    @property
    def gravidade(self) -> str:
        """Bloqueante quando toca critério ou decisão, ou quando foi o orquestrador quem viu falhar; senão acompanhamento."""
        if self.toca or self.origem == ORIGEM_DO_ORQUESTRADOR:
            return a.GRAVIDADE_BLOQUEANTE
        return a.GRAVIDADE_ACOMPANHAMENTO

    def em_json(self) -> dict[str, Any]:
        """O achado para a lista de pendências e para o nó Achado."""
        return {"gravidade": self.gravidade, "titulo": self.titulo, "descricao": self.descricao, "prova": self.prova,
                "local": self.local, "criterios": list(self.criterios), "decisoes": list(self.decisoes),
                "severidade": self.severidade, "origem": self.origem}

    @classmethod
    def de_json(cls, dados: Mapping[str, Any]) -> "Achado":
        """O achado como o verificador o devolveu."""
        return cls(
            titulo=str(dados["titulo"]).strip(), descricao=str(dados["descricao"]).strip(),
            prova=str(dados.get("prova", "")).strip(), local=str(dados.get("local", "")).strip(),
            criterios=_textos(dados.get("criterios")), decisoes=_textos(dados.get("decisoes")),
            severidade=str(dados.get("severidade", "")),
        )


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


def _parecer(item: Mapping[str, Any]) -> Parecer:
    """Um parecer do JSON."""
    return Parecer(str(item["id"]).strip(), str(item["veredito"]), str(item["prova"]).strip())


@dataclass(frozen=True)
class Verificacao:
    """O que o verificador devolveu de um marco, ou do Goal inteiro na verificação final."""

    resumo: str
    criterios: tuple[Parecer, ...]
    decisoes: tuple[Parecer, ...] = ()
    achados: tuple[Achado, ...] = field(default_factory=tuple)
    comandos: tuple[ComandoRodado, ...] = ()

    @classmethod
    def de_json(cls, dados: Mapping[str, Any]) -> "Verificacao":
        """A verificação como o verificador a devolveu."""
        return cls(
            resumo=str(dados["resumo"]).strip(),
            criterios=tuple(_parecer(item) for item in dados["criterios"]),
            decisoes=tuple(_parecer(item) for item in dados.get("decisoes", [])),
            achados=tuple(Achado.de_json(item) for item in dados["achados"]),
            comandos=_comandos(dados.get("comandos")),
        )

    def com_achado_do_orquestrador(self, titulo: str, descricao: str, criterios: tuple[str, ...] = ()) -> "Verificacao":
        """A verificação com o que o orquestrador viu falhar no commit verificado (a suíte, um teste de aceite)."""
        achado = Achado(titulo, descricao, descricao[-LIMITE_DA_PROVA:], criterios=criterios, origem=ORIGEM_DO_ORQUESTRADOR)
        return replace(self, achados=(*self.achados, achado))

    def com_parecer(self, id_criterio: str, veredito: str, prova: str) -> "Verificacao":
        """A verificação com o parecer do critério trocado pelo que o orquestrador viu."""
        pareceres = tuple(Parecer(id_criterio, veredito, prova) if p.id == id_criterio else p for p in self.criterios)
        return replace(self, criterios=pareceres)

    def bloqueantes(self) -> tuple[Achado, ...]:
        """Os achados bloqueantes e, para o critério ou decisão sem `atende` que nenhum achado toca, um sintético."""
        declarados = tuple(achado for achado in self.achados if achado.gravidade == a.GRAVIDADE_BLOQUEANTE)
        tocados = {id_c for achado in self.achados for id_c in achado.toca}
        sinteticos = tuple(
            Achado(f"{parecer.id} {parecer.veredito}", parecer.prova, parecer.prova, "", *_lados(parecer.id),
                   origem=ORIGEM_DO_ORQUESTRADOR)
            for parecer in (*self.criterios, *self.decisoes)
            if parecer.veredito != a.VEREDITO_QUE_ATENDE and parecer.id not in tocados
        )
        return declarados + sinteticos

    def acompanhamentos(self) -> tuple[Achado, ...]:
        """Os achados que não tocam critério nem decisão."""
        return tuple(achado for achado in self.achados if achado.gravidade == a.GRAVIDADE_ACOMPANHAMENTO)

    def achados_finais(self) -> tuple[Achado, ...]:
        """Os bloqueantes e depois os acompanhamentos, na ordem em que viram nós Achado."""
        return self.bloqueantes() + self.acompanhamentos()


def _lados(id_parecer: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """O parecer de critério toca o critério; o de decisão (D...), a decisão."""
    return ((), (id_parecer,)) if id_parecer.upper().startswith("D") else ((id_parecer,), ())


def conferir_verificacao(verificacao: Verificacao, criterios: Sequence[str], decisoes: Sequence[str]) -> tuple[str, ...]:
    """Um parecer por critério e por decisão pedidos, achado que toca só o que existe e ao menos um comando rodado."""
    dados = [parecer.id for parecer in verificacao.criterios]
    dadas = [parecer.id for parecer in verificacao.decisoes]
    conhecidos = {*criterios, *decisoes}
    return (
        *(() if verificacao.comandos else ("a verificacao nao lista nenhum comando rodado em 'comandos'",)),
        *(f"falta o parecer do criterio {id_c}" for id_c in criterios if id_c not in dados),
        *(f"falta o parecer da decisao {id_d}" for id_d in decisoes if id_d not in dadas),
        *(f"parecer {id_p} repetido" for id_p in sorted({i for i in dados + dadas if (dados + dadas).count(i) > 1})),
        *(
            f"o achado '{achado.titulo}' toca {id_c}, que nao e criterio nem decisao desta verificacao"
            for achado in verificacao.achados for id_c in achado.toca if id_c not in conhecidos
        ),
    )
