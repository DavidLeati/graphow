"""Modelos imutáveis do catálogo de código extraído do repositório."""

from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParametroDocumentado:
    """Parâmetro de uma função, com o tipo declarado na assinatura."""

    nome: str
    anotacao: str

    def formatar(self) -> str:
        """Representação textual do parâmetro na assinatura."""
        return f"{self.nome}: {self.anotacao}"


@dataclass(frozen=True)
class FuncaoDocumentada:
    """Função ou método com assinatura tipada e resumo da docstring."""

    nome: str
    parametros: tuple[ParametroDocumentado, ...]
    retorno: str
    resumo: str
    linhas: int
    eh_publica: bool
    eh_propriedade: bool = False
    eh_abstrata: bool = False

    def formatar_assinatura(self) -> str:
        """Assinatura completa em uma linha, pronta para o catálogo."""
        argumentos = ", ".join(parametro.formatar() for parametro in self.parametros)
        return f"{self.nome}({argumentos}) -> {self.retorno}"

    @property
    def marcadores(self) -> tuple[str, ...]:
        """Rótulos curtos que qualificam a função no catálogo."""
        rotulos: list[str] = []
        if self.eh_propriedade:
            rotulos.append("property")
        if self.eh_abstrata:
            rotulos.append("abstract")
        return tuple(rotulos)


@dataclass(frozen=True)
class ClasseDocumentada:
    """Classe com suas bases, atributos de dados e métodos públicos."""

    nome: str
    bases: tuple[str, ...]
    resumo: str
    metodos: tuple[FuncaoDocumentada, ...]
    campos: tuple[ParametroDocumentado, ...]
    eh_imutavel: bool
    eh_abstrata: bool

    @property
    def metodos_publicos(self) -> tuple[FuncaoDocumentada, ...]:
        """Métodos que compõem o contrato externo da classe."""
        return tuple(metodo for metodo in self.metodos if metodo.eh_publica)

    @property
    def natureza(self) -> str:
        """Classificação curta da classe, para leitura de relance."""
        if self.eh_abstrata:
            return "contrato"
        if self.eh_imutavel:
            return "DTO imutável"
        return "serviço"


@dataclass(frozen=True)
class ConstanteDocumentada:
    """Constante de módulo com tipo e valor declarados."""

    nome: str
    anotacao: str
    valor: str


@dataclass(frozen=True)
class ModuloDocumentado:
    """Um arquivo Python do pacote, com tudo que ele expõe."""

    caminho_relativo: str
    nome_modulo: str
    resumo: str
    linhas: int
    classes: tuple[ClasseDocumentada, ...] = field(default_factory=tuple)
    funcoes: tuple[FuncaoDocumentada, ...] = field(default_factory=tuple)
    constantes: tuple[ConstanteDocumentada, ...] = field(default_factory=tuple)

    @property
    def funcoes_publicas(self) -> tuple[FuncaoDocumentada, ...]:
        """Funções de módulo que fazem parte da superfície pública."""
        return tuple(funcao for funcao in self.funcoes if funcao.eh_publica)

    @property
    def esta_vazio(self) -> bool:
        """Um módulo sem classes, funções ou constantes não rende dossiê."""
        return not (self.classes or self.funcoes_publicas or self.constantes)


@dataclass(frozen=True)
class SetorDocumentado:
    """Uma ala temática da biblioteca, correspondente a um pacote do código."""

    numero: int
    identificador: str
    titulo: str
    missao: str
    modulos: tuple[ModuloDocumentado, ...]

    @property
    def nome_arquivo(self) -> str:
        """Nome do dossiê deste setor dentro de docs/setores/."""
        return f"{self.numero:02d}_{self.identificador}.md"

    @property
    def total_linhas(self) -> int:
        """Soma das linhas de todos os módulos do setor."""
        return sum(modulo.linhas for modulo in self.modulos)

    @property
    def total_classes(self) -> int:
        """Quantidade de classes catalogadas no setor."""
        return sum(len(modulo.classes) for modulo in self.modulos)

    @property
    def modulos_com_conteudo(self) -> tuple[ModuloDocumentado, ...]:
        """Módulos que têm algo a documentar."""
        return tuple(modulo for modulo in self.modulos if not modulo.esta_vazio)


@dataclass(frozen=True)
class CatalogoRepositorio:
    """Catálogo completo, pronto para renderização."""

    setores: tuple[SetorDocumentado, ...]

    @property
    def total_modulos(self) -> int:
        """Quantidade de módulos Python catalogados."""
        return sum(len(setor.modulos) for setor in self.setores)

    @property
    def total_linhas(self) -> int:
        """Total de linhas de código catalogadas."""
        return sum(setor.total_linhas for setor in self.setores)

    @property
    def total_classes(self) -> int:
        """Total de classes catalogadas."""
        return sum(setor.total_classes for setor in self.setores)


def resumir_docstring(docstring: str | None) -> str:
    """Extrai a primeira frase da docstring, que é o resumo canônico do elemento."""
    if not docstring:
        return ""
    primeira_linha = docstring.strip().split("\n", 1)[0].strip()
    return primeira_linha


def ordenar_por_nome(elementos: Sequence[ClasseDocumentada]) -> tuple[ClasseDocumentada, ...]:
    """Ordena classes por nome, para o catálogo sair estável entre execuções."""
    return tuple(sorted(elementos, key=lambda elemento: elemento.nome))
