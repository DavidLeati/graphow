"""Os dados versionados da bancada: projetos, prompts e linha de base, lidos de `bancada/`.

Cada projeto é uma pasta com a semente (a árvore do commit inicial do
laboratório), a spec, as sondas e um `projeto.json` com o ramo de trabalho e a
identidade do commit da semente. Os prompts são modelos com marcadores
`{NOME}`; o preenchimento recusa marcador sem valor e valor sem marcador, para
que um prompt mexido não rode calado com um pedaço faltando.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from graphow.core.exceptions import GraphowError

RAIZ_DA_BANCADA_PADRAO: Path = Path(__file__).resolve().parents[3] / "bancada"
PASTA_DOS_PROJETOS: str = "projetos"
PASTA_DAS_ARQUITETURAS: str = "arquiteturas"
ARQUIVO_DO_PROJETO: str = "projeto.json"
ARQUIVO_DA_SPEC: str = "spec.md"
ARQUIVO_DAS_SONDAS: str = "sondas.md"
PASTA_DA_SEMENTE: str = "semente"
ARQUIVO_DO_AUDITOR: str = "auditor.md"
ARQUIVO_DA_LINHA_DE_BASE: str = "linha-de-base.json"
EXTENSAO_DO_MODELO: str = ".md"
PADRAO_DE_MARCADOR: re.Pattern[str] = re.compile(r"\{([A-Z][A-Z_]*)\}")
PADRAO_DE_AUTOR: re.Pattern[str] = re.compile(r"^(?P<nome>[^<]+?)\s*<(?P<email>[^>]+)>$")


class ErroDaBancada(GraphowError):
    """Os dados da bancada não servem para o que foi pedido."""


@dataclass(frozen=True)
class Semente:
    """O commit inicial do projeto no laboratório: o que o repositório da execução reproduz."""

    commit: str
    arvore: str
    ramo: str
    mensagem: str
    autor: str
    data: str

    @property
    def nome_do_autor(self) -> str:
        """O nome antes do e-mail em `Nome <email>`."""
        return self._autor_em_partes()["nome"]

    @property
    def email_do_autor(self) -> str:
        """O e-mail entre os sinais de `Nome <email>`."""
        return self._autor_em_partes()["email"]

    def _autor_em_partes(self) -> Mapping[str, str]:
        """Nome e e-mail do autor, ou a recusa quando ele não está no formato do git."""
        casamento = PADRAO_DE_AUTOR.match(self.autor)
        if casamento is None:
            raise ErroDaBancada("autor da semente fora do formato 'Nome <email>'", {"autor": self.autor})
        return casamento.groupdict()


@dataclass(frozen=True)
class ProjetoDaBancada:
    """Uma demanda do laboratório: a pasta dela, o ramo de trabalho e a semente."""

    nome: str
    descricao: str
    ramo: str
    semente: Semente
    pasta: Path

    @property
    def spec(self) -> Path:
        """O pedido, as perguntas do analista e as respostas do humano."""
        return self.pasta / ARQUIVO_DA_SPEC

    @property
    def sondas(self) -> Path:
        """Os casos que deram defeito numa das implementações, que o auditor confere em todas."""
        return self.pasta / ARQUIVO_DAS_SONDAS

    @property
    def pasta_da_semente(self) -> Path:
        """A árvore do commit inicial, sem `.git`."""
        return self.pasta / PASTA_DA_SEMENTE

    def texto_das_sondas(self) -> str:
        """A lista de sondas como entra no prompt do auditor, sem a quebra final."""
        return self.sondas.read_text(encoding="utf-8").rstrip("\n")


@dataclass(frozen=True)
class Bancada:
    """A pasta `bancada/`: onde os projetos, os prompts e a linha de base estão."""

    raiz: Path = RAIZ_DA_BANCADA_PADRAO

    @property
    def linha_de_base(self) -> Path:
        """Os números do laboratório contra os quais o placar compara."""
        return self.raiz / ARQUIVO_DA_LINHA_DE_BASE

    def projetos(self) -> tuple[ProjetoDaBancada, ...]:
        """Todo projeto com `projeto.json`, em ordem de nome."""
        pastas = sorted((self.raiz / PASTA_DOS_PROJETOS).glob(f"*/{ARQUIVO_DO_PROJETO}"))
        if not pastas:
            raise ErroDaBancada("nenhum projeto na bancada", {"raiz": str(self.raiz)})
        return tuple(_ler_projeto(caminho.parent) for caminho in pastas)

    def projeto(self, nome: str) -> ProjetoDaBancada:
        """O projeto pelo nome; a recusa lista os que existem."""
        por_nome = {projeto.nome: projeto for projeto in self.projetos()}
        if nome not in por_nome:
            raise ErroDaBancada("projeto desconhecido na bancada", {"projeto": nome, "existentes": ", ".join(por_nome)})
        return por_nome[nome]

    def modelo_da_arquitetura(self, nome: str) -> str:
        """O prompt modelo de uma arquitetura que roda por prompt, como a enxuta."""
        return _ler_texto(self.raiz / PASTA_DAS_ARQUITETURAS / f"{nome}{EXTENSAO_DO_MODELO}")

    def modelo_do_auditor(self) -> str:
        """O prompt modelo do auditor, com `{REPO}`, `{SPEC}`, `{RAMO}` e `{SONDAS}`."""
        return _ler_texto(self.raiz / ARQUIVO_DO_AUDITOR)


def preencher_modelo(modelo: str, valores: Mapping[str, str]) -> str:
    """O modelo com cada `{NOME}` trocado pelo valor; marcador ou valor sobrando recusa."""
    marcadores = set(PADRAO_DE_MARCADOR.findall(modelo))
    faltando, sobrando = sorted(marcadores - set(valores)), sorted(set(valores) - marcadores)
    if faltando or sobrando:
        raise ErroDaBancada(
            "modelo e valores nao casam",
            {"sem_valor": ", ".join(faltando), "sem_marcador": ", ".join(sobrando)},
        )
    return PADRAO_DE_MARCADOR.sub(lambda casamento: valores[casamento.group(1)], modelo)


def _ler_projeto(pasta: Path) -> ProjetoDaBancada:
    """O `projeto.json` da pasta como projeto da bancada."""
    dados = _ler_json(pasta / ARQUIVO_DO_PROJETO)
    try:
        semente = Semente(**dados["semente"])
        return ProjetoDaBancada(dados["nome"], dados["descricao"], dados["ramo"], semente, pasta)
    except (KeyError, TypeError) as erro:
        raise ErroDaBancada("projeto.json incompleto", {"projeto": pasta.name, "erro": str(erro)}) from erro


def _ler_json(caminho: Path) -> Any:
    """Um JSON dos dados da bancada; ausente ou ilegível recusa com o caminho."""
    try:
        return json.loads(_ler_texto(caminho))
    except json.JSONDecodeError as erro:
        raise ErroDaBancada("JSON ilegivel na bancada", {"arquivo": str(caminho), "erro": str(erro)}) from erro


def _ler_texto(caminho: Path) -> str:
    """Um arquivo de texto da bancada, em UTF-8."""
    try:
        return caminho.read_text(encoding="utf-8")
    except OSError as erro:
        raise ErroDaBancada("arquivo da bancada ausente", {"arquivo": str(caminho)}) from erro
