"""A saída do autor de aceite e a conferência dela: a forma, o lugar dos testes e o vermelho de antes da implementação.

O autor de aceite é uma sessão separada do executor: depois do plano, ele
escreve os testes que provam cada critério `teste` (um ou mais por critério,
cada um citando o código do critério no nome ou na docstring) e a lista de
checagem de cada critério `checagem`, e devolve, por critério, os testes
(arquivo, nome e o comando que roda só ele), a checagem e, quando o código já
atendia o critério, a justificativa; e o comando que roda só os testes de
aceite. Os testes moram em `aceite/`, como arquivos novos: é o que o executor
não pode tocar, e o que a suíte do plano roda sem.

O orquestrador confere tudo antes de commitar: cada critério do plano tem a
sua entrada, cada teste existe em `aceite/`, tem o nome no arquivo e cita o
critério, e o autor não mexeu em nada fora de `aceite/`. E roda cada teste: o
teste que já passa sem implementação é sinalizado, porque ou o critério já era
atendido pelo código (e a justificativa diz por quê), ou o teste não prova
nada; e o que falha tem de falhar numa asserção dele, lida na saída do runner
(orquestrador/resultado_de_teste.py), e não por import, coleta, comando ou
nome errado. O que não confere volta à mesma sessão, uma vez.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from graphow.core import aceite as a
from graphow.orquestrador.resultado_de_teste import por_que_nao_passou, por_que_o_vermelho_nao_vale
from graphow.orquestrador.suite import ResultadoDaSuite

PASTA_DO_ACEITE: str = "aceite"
# O que rodar testes deixa para trás e não é de ninguém: não conta como mudança do
# autor, não vira arquivo protegido e não entra no commit dos testes.
PASTAS_DE_CACHE: frozenset[str] = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules"})
SUFIXOS_DE_CACHE: tuple[str, ...] = (".pyc", ".pyo")
LIMITE_DA_SAIDA_REGISTRADA: int = 600

Rodar = Callable[[str], ResultadoDaSuite]


def _textos(valor: object) -> tuple[str, ...]:
    """A lista de textos do JSON, sem vazios."""
    return tuple(str(item).strip() for item in valor if str(item).strip()) if isinstance(valor, list) else ()


@dataclass(frozen=True)
class TesteDeAceite:
    """Um teste de aceite: o arquivo, o nome e o comando que roda só ele."""

    arquivo: str
    nome: str
    comando: str

    def em_json(self) -> dict[str, str]:
        """O teste para o livro-razão."""
        return {"arquivo": self.arquivo, "nome": self.nome, "comando": self.comando}


@dataclass(frozen=True)
class AceiteDoCriterio:
    """O que prova um critério: os testes, a checagem e, quando o código já o atendia, por quê."""

    id: str
    testes: tuple[TesteDeAceite, ...] = ()
    checagem: tuple[str, ...] = ()
    ja_atendido: str = ""

    def em_json(self) -> dict[str, Any]:
        """O aceite do critério para o livro-razão."""
        return {"testes": [teste.em_json() for teste in self.testes], "checagem": list(self.checagem), "ja_atendido": self.ja_atendido}


@dataclass(frozen=True)
class SaidaDoAceite:
    """O que o autor de aceite devolveu."""

    resumo: str
    comando_aceite: str
    criterios: tuple[AceiteDoCriterio, ...]

    @classmethod
    def de_json(cls, dados: Mapping[str, Any]) -> "SaidaDoAceite":
        """A saída como o autor a devolveu, já conferida pelo schema."""
        return cls(
            resumo=str(dados["resumo"]).strip(),
            comando_aceite=str(dados["comando_aceite"]).strip(),
            criterios=tuple(
                AceiteDoCriterio(
                    id=str(c["id"]).strip(),
                    testes=tuple(TesteDeAceite(str(t["arquivo"]).strip().replace("\\", "/"), str(t["nome"]).strip(),
                                               str(t["comando"]).strip()) for t in c.get("testes", [])),
                    checagem=_textos(c.get("checagem")),
                    ja_atendido=str(c.get("ja_atendido", "")).strip(),
                )
                for c in dados["criterios"]
            ),
        )

    @classmethod
    def do_livro(cls, aceite: Mapping[str, Any] | None) -> "SaidaDoAceite":
        """Os testes de aceite como o Goal os guarda; vazio quando ainda não há."""
        if not aceite:
            return cls("", "", ())
        return cls.de_json({"resumo": aceite.get("resumo", ""), "comando_aceite": aceite.get("comando", ""),
                            "criterios": aceite.get("criterios", [])})

    def do_criterio(self, id_criterio: str) -> AceiteDoCriterio | None:
        """O aceite de um critério, pelo código."""
        return next((criterio for criterio in self.criterios if criterio.id == id_criterio), None)

    def testes(self) -> Iterable[tuple[AceiteDoCriterio, TesteDeAceite]]:
        """Cada teste com o critério que ele prova."""
        return ((criterio, teste) for criterio in self.criterios for teste in criterio.testes)


def conferir_forma(saida: SaidaDoAceite, criterios: Mapping[str, str], area: Path, *, mudados: Sequence[str]) -> tuple[str, ...]:
    """Uma entrada por critério do plano, o teste certo para o critério `teste`, a checagem para o `checagem` e tudo em aceite/."""
    return (
        *(f"falta o aceite do criterio {id_c}" for id_c in criterios if saida.do_criterio(id_c) is None),
        *(f"o criterio {c.id} nao e do plano" for c in saida.criterios if c.id not in criterios),
        *(f"o criterio {id_c} se prova por teste e nao tem teste" for id_c, tipo in criterios.items()
          if tipo == a.VERIFICACAO_POR_TESTE and (c := saida.do_criterio(id_c)) is not None and not c.testes),
        *(f"o criterio {id_c} se prova por checagem e nao tem a lista em 'checagem'" for id_c, tipo in criterios.items()
          if tipo == a.VERIFICACAO_POR_CHECAGEM and (c := saida.do_criterio(id_c)) is not None and not c.checagem),
        *(problema for criterio, teste in saida.testes() for problema in _problemas_do_teste(criterio.id, teste, area)),
        *(f"{caminho} foi criado ou mudado fora de {PASTA_DO_ACEITE}/: o autor de aceite so cria arquivos novos ali"
          for caminho in mudados if not dentro_do_aceite(caminho)),
    )


def e_cache(caminho: str) -> bool:
    """O caminho é de cache que a execução dos testes deixa (bytecode, cache do pytest, dependências instaladas)."""
    partes = caminho.replace("\\", "/").split("/")
    return bool(PASTAS_DE_CACHE & set(partes)) or caminho.endswith(SUFIXOS_DE_CACHE)


def dentro_do_aceite(caminho: str) -> bool:
    """O caminho, relativo à raiz, está na pasta dos testes de aceite."""
    return caminho.replace("\\", "/").strip("/").startswith(f"{PASTA_DO_ACEITE}/")


def _problemas_do_teste(id_criterio: str, teste: TesteDeAceite, area: Path) -> list[str]:
    """O arquivo existe em aceite/, tem o nome do teste e cita o critério."""
    if not dentro_do_aceite(teste.arquivo):
        return [f"o teste {teste.nome} de {id_criterio} esta em {teste.arquivo}, fora de {PASTA_DO_ACEITE}/"]
    caminho = area / teste.arquivo
    if not caminho.is_file():
        return [f"o arquivo {teste.arquivo} do teste {teste.nome} de {id_criterio} nao existe"]
    conteudo = caminho.read_text(encoding="utf-8", errors="replace")
    problemas = [] if teste.nome.split("::")[-1] in conteudo else [f"o teste {teste.nome} nao aparece em {teste.arquivo}"]
    cita = id_criterio.lower() in teste.nome.lower() or re.search(rf"\b{re.escape(id_criterio)}\b", conteudo) is not None
    return problemas + ([] if cita else [f"o teste {teste.nome} nao cita {id_criterio} no nome nem no arquivo"])


@dataclass(frozen=True)
class ExecucaoDeAceite:
    """Um teste de aceite rodado pelo orquestrador: o critério, o teste, o comando e como saiu."""

    criterio: str
    teste: str
    comando: str
    codigo: int | None
    saida: str

    @property
    def motivo(self) -> str:
        """Por que o teste não conta como verde (saiu com erro, foi pulado, o runner não disse); vazio quando conta."""
        return por_que_nao_passou(self.comando, self.codigo, self.saida)

    @property
    def passou(self) -> bool:
        """Saiu com zero e a saída do runner diz que passou, sem pular nada."""
        return not self.motivo

    def vermelho_invalido(self) -> str:
        """Por que a falha não é a asserção do teste declarado; vazio quando é."""
        return por_que_o_vermelho_nao_vale(self.comando, self.codigo, self.saida, nome=self.teste)

    def em_json(self) -> dict[str, Any]:
        """A execução para o livro-razão."""
        return {"criterio": self.criterio, "teste": self.teste, "comando": self.comando, "codigo": self.codigo,
                "passou": self.passou, "motivo": self.motivo, "saida": self.saida[-LIMITE_DA_SAIDA_REGISTRADA:]}


def rodar_testes(saida: SaidaDoAceite, rodar: Rodar, criterios: Iterable[str] | None = None) -> tuple[ExecucaoDeAceite, ...]:
    """Cada teste de aceite dos critérios dados (todos, sem eles), rodado pelo comando dele."""
    escolhidos = None if criterios is None else set(criterios)
    return tuple(
        _execucao(criterio.id, teste.nome, teste.comando, rodar=rodar)
        for criterio, teste in saida.testes() if escolhidos is None or criterio.id in escolhidos
    )


def rodar_o_comando_de_aceite(saida: SaidaDoAceite, rodar: Rodar) -> ExecucaoDeAceite:
    """O comando que roda todos os testes de aceite, de uma vez."""
    return _execucao("", "comando_aceite", saida.comando_aceite, rodar=rodar)


def _execucao(criterio: str, teste: str, comando: str, *, rodar: Rodar) -> ExecucaoDeAceite:
    """Um comando rodado como execução de aceite."""
    resultado = rodar(comando)
    codigo = None if resultado.tempo_esgotado else resultado.codigo
    return ExecucaoDeAceite(criterio, teste, comando, codigo, resultado.saida)


def _vermelho_errado(execucao: ExecucaoDeAceite, motivo: str) -> str:
    """O problema do teste vermelho pelo motivo errado, para a nova tentativa do autor."""
    return (f"o teste {execucao.teste} de {execucao.criterio} esta vermelho pelo motivo errado: {motivo}. Antes da "
            "implementacao ele tem de rodar e falhar numa assercao dele: importe o que ainda nao existe dentro do teste e "
            "transforme a ausencia em assert, sem skip, xfail nem todo, e com o resumo do runner na saida")


def conferir_vermelho(saida: SaidaDoAceite, rodar: Rodar) -> tuple[tuple[str, ...], tuple[ExecucaoDeAceite, ...]]:
    """Os testes falham antes da implementação, salvo o do critério que já era atendido; devolve os problemas e as execuções."""
    execucoes = rodar_testes(saida, rodar)
    ja_atendidos = {criterio.id for criterio in saida.criterios if criterio.ja_atendido}
    problemas = [
        (f"o teste {e.teste} de {e.criterio} ja passa sem implementacao: ou o criterio ja era atendido pelo codigo "
         "(diga por que em 'ja_atendido'), ou o teste nao prova nada (corrija-o para falhar enquanto o criterio nao for atendido)")
        if e.passou else
        f"o teste {e.teste} de {e.criterio} nao passa ({e.motivo}), mas 'ja_atendido' diz que o codigo ja atende {e.criterio}"
        for e in execucoes if e.passou != (e.criterio in ja_atendidos)
    ]
    problemas += [_vermelho_errado(e, motivo) for e in execucoes
                  if not e.passou and e.criterio not in ja_atendidos and (motivo := e.vermelho_invalido())]
    todos_atendidos = bool(execucoes) and all(e.criterio in ja_atendidos for e in execucoes)
    agregado = rodar_o_comando_de_aceite(saida, rodar) if execucoes else None
    if agregado is not None and agregado.passou != todos_atendidos:
        estado = "passa" if agregado.passou else "falha"
        problemas.append(f"o comando_aceite `{saida.comando_aceite}` {estado}, e devia {'passar' if todos_atendidos else 'falhar'} "
                         "agora: ele roda so os testes de aceite, todos eles")
    return tuple(problemas), execucoes + ((agregado,) if agregado is not None else ())
